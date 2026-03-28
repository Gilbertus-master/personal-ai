"""
Automated code fixer — one Claude Code session per finding.

Picks the highest-severity unresolved finding from code_review_findings,
launches a dedicated `claude -p` session to fix it, verifies the fix,
and marks it resolved. Changes are left uncommitted for manual review.

Cron: every 15 min during work hours (8-22 CET), 1 fix per run.
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
import subprocess
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
_dotenv_vars = dotenv_values(PROJECT_DIR / ".env")
FIX_PROMPT_PATH = PROJECT_DIR / "scripts" / "fix_prompt.md"
MODEL = os.getenv("CODE_FIX_MODEL", "sonnet")
BUDGET_PER_FIX = float(os.getenv("CODE_FIX_BUDGET", "0.50"))

ALLOWED_PREFIXES = ("app/", "scripts/", "mcp_gilbertus/")

SEVERITY_ORDER = """
    CASE severity
        WHEN 'critical' THEN 0
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'low' THEN 3
        ELSE 99
    END
"""


def _ensure_schema() -> None:
    """Add fix_attempted_at column if missing (prevents infinite retry loops)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE code_review_findings
                ADD COLUMN IF NOT EXISTS fix_attempted_at TIMESTAMPTZ
            """)
        conn.commit()


def _get_next_finding() -> dict | None:
    """Get the single highest-priority unresolved finding."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, file_path, severity, category, title, description,
                       line_start, line_end, suggested_fix
                FROM code_review_findings
                WHERE resolved = FALSE
                  AND severity IN ('critical', 'high', 'medium', 'low')
                  AND (fix_attempted_at IS NULL
                       OR fix_attempted_at < NOW() - INTERVAL '24 hours')
                ORDER BY {SEVERITY_ORDER}, created_at ASC
                LIMIT 1
            """)
            rows = cur.fetchall()
            if not rows:
                return None
            r = rows[0]
            return {
                "id": r[0], "file_path": r[1], "severity": r[2],
                "category": r[3], "title": r[4], "description": r[5],
                "line_start": r[6], "line_end": r[7], "suggested_fix": r[8],
            }


def _validate_file_path(file_path: str) -> bool:
    """Safety check — only fix files in allowed directories."""
    if ".." in file_path:
        log.warning("path_traversal_blocked", file_path=file_path)
        return False
    if not any(file_path.startswith(p) for p in ALLOWED_PREFIXES):
        log.warning("file_outside_allowed_dirs", file_path=file_path)
        return False
    if not (PROJECT_DIR / file_path).exists():
        log.warning("file_not_found", file_path=file_path)
        return False
    return True


def _build_user_prompt(finding: dict) -> str:
    """Construct the user prompt from finding data."""
    lines_info = ""
    if finding["line_start"]:
        end = finding["line_end"] or finding["line_start"]
        lines_info = f"\n**Lines**: {finding['line_start']}-{end}"

    suggested = finding["suggested_fix"] or "No specific fix suggested — use your judgment."

    abs_file = str(PROJECT_DIR / finding["file_path"])

    # Give precise read instructions to avoid reading huge files fully
    if finding["line_start"]:
        line_s = max(1, finding["line_start"] - 10)
        line_e = (finding["line_end"] or finding["line_start"]) + 10
        read_instruction = (
            f"1. Read the relevant section: Read {abs_file} "
            f"from line {line_s} to {line_e} (offset={line_s}, limit={line_e - line_s + 1}). "
            f"Also read the first 30 lines for imports/context (offset=1, limit=30)."
        )
    else:
        read_instruction = f"1. Read the file {abs_file} with the Read tool"

    return (
        f"The project is at {PROJECT_DIR}. "
        f"Fix the following issue in {abs_file}:\n\n"
        f"**Severity**: {finding['severity']}\n"
        f"**Category**: {finding['category']}\n"
        f"**Title**: {finding['title']}\n\n"
        f"**Description**:\n{finding['description']}\n"
        f"{lines_info}\n\n"
        f"**Suggested fix**:\n{suggested}\n\n"
        f"Steps:\n"
        f"{read_instruction}\n"
        f"2. Apply the fix using the Edit tool — minimal change only\n"
        f"3. Run: ruff check {finding['file_path']}\n"
        f"4. Run: git diff\n"
        f"5. Output ONLY the JSON result (no markdown fences, no extra text)"
    )


def _launch_fix_session(finding: dict, system_prompt: str) -> dict | None:
    """Launch a dedicated claude -p session to fix one finding."""
    user_prompt = _build_user_prompt(finding)

    cmd = [
        "claude", "-p",
        "--bare",
        "--model", MODEL,
        "--max-budget-usd", str(BUDGET_PER_FIX),
        "--system-prompt", system_prompt,
        "--output-format", "json",
        "--allow-dangerously-skip-permissions",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--add-dir", str(PROJECT_DIR),
        "--allowedTools", "Read,Grep,Edit,Bash(git:*,ruff:*)",
        "--", user_prompt,
    ]

    log.info("launching_fix",
             finding_id=finding["id"],
             file_path=finding["file_path"],
             severity=finding["severity"],
             title=finding["title"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(PROJECT_DIR),
            env={**os.environ, **_dotenv_vars, "CLAUDE_CODE_SIMPLE": "1"},
        )

        raw_output = result.stdout.strip()

        if result.returncode != 0:
            log.error("fix_session_failed",
                      finding_id=finding["id"],
                      returncode=result.returncode,
                      stderr=result.stderr[:500])
            return None

        # Parse JSON wrapper from --output-format json
        wrapper = json.loads(raw_output)
        json_str = wrapper.get("result", "")
        cost = wrapper.get("total_cost_usd", 0)

        if wrapper.get("is_error"):
            log.error("fix_session_error",
                      finding_id=finding["id"],
                      error=json_str[:500])
            return None

        # Try to extract structured JSON from response
        try:
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = json_str[start:end]

            data = json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            # Agent didn't return structured JSON — infer from session success
            # and verify independently
            log.warning("fix_no_json_response", finding_id=finding["id"],
                        result_preview=wrapper.get("result", "")[:200])
            data = {
                "fixed": True,
                "changes_summary": wrapper.get("result", "")[:200],
                "files_modified": [finding["file_path"]],
            }

        log.info("fix_session_completed",
                 finding_id=finding["id"],
                 fixed=data.get("fixed"),
                 cost_usd=round(cost, 4))
        return data

    except subprocess.TimeoutExpired:
        log.error("fix_timeout", finding_id=finding["id"])
        return None
    except json.JSONDecodeError as e:
        log.error("fix_json_parse_failed",
                  finding_id=finding["id"],
                  error=str(e),
                  raw=raw_output[:500] if raw_output else "empty")
        return None
    except Exception as e:
        log.error("fix_unexpected_error", finding_id=finding["id"], error=str(e))
        return None


def _verify_fix(file_path: str, ruff_baseline: int = 0) -> tuple[bool, str]:
    """Post-fix verification: ruff (only new errors) + git diff."""
    # Check ruff for Python files — only fail if NEW errors were introduced
    if file_path.endswith(".py"):
        try:
            ruff_result = subprocess.run(
                [".venv/bin/ruff", "check", file_path],
                capture_output=True, text=True, timeout=30,
                cwd=str(PROJECT_DIR),
            )
            current_errors = ruff_result.stdout.count("\n") if ruff_result.stdout.strip() else 0
            if current_errors > ruff_baseline:
                return False, f"ruff: {current_errors - ruff_baseline} new errors introduced: {ruff_result.stdout[:500]}"
        except Exception as e:
            log.warning("ruff_check_failed", error=str(e))

    # Check git diff — ensure something actually changed
    try:
        diff_result = subprocess.run(
            ["git", "diff", "--stat", "--", file_path],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_DIR),
        )
        if not diff_result.stdout.strip():
            return False, "no changes detected in file"
        return True, diff_result.stdout.strip()
    except Exception as e:
        return False, f"git diff failed: {e}"


def _revert_files(file_paths: list[str]) -> None:
    """Revert files to their git state."""
    for fp in file_paths:
        try:
            subprocess.run(
                ["git", "checkout", "--", fp],
                capture_output=True, text=True, timeout=10,
                cwd=str(PROJECT_DIR),
            )
            log.warning("fix_reverted", file_path=fp)
        except Exception:
            log.error("revert_failed", file_path=fp)


def _mark_resolved(finding_id: int) -> None:
    """Mark finding as resolved in DB."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE code_review_findings
                SET resolved = TRUE, resolved_at = NOW()
                WHERE id = %s
            """, (finding_id,))
        conn.commit()


def _mark_attempted(finding_id: int) -> None:
    """Mark finding as attempted (prevents retry for 24h)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE code_review_findings
                SET fix_attempted_at = NOW()
                WHERE id = %s
            """, (finding_id,))
        conn.commit()


def run() -> dict:
    """Main entry: pick one finding, fix it, verify, mark resolved."""
    _ensure_schema()

    finding = _get_next_finding()
    if not finding:
        log.info("no_unresolved_findings")
        return {"status": "idle", "fixed": False}

    if not _validate_file_path(finding["file_path"]):
        _mark_attempted(finding["id"])
        return {"status": "skipped", "fixed": False,
                "reason": "file_path not in allowed dirs"}

    system_prompt = FIX_PROMPT_PATH.read_text(encoding="utf-8")

    # Capture ruff baseline BEFORE fix (to detect only NEW errors)
    ruff_baseline = 0
    if finding["file_path"].endswith(".py"):
        try:
            pre_ruff = subprocess.run(
                [".venv/bin/ruff", "check", finding["file_path"]],
                capture_output=True, text=True, timeout=30,
                cwd=str(PROJECT_DIR),
            )
            ruff_baseline = pre_ruff.stdout.count("\n") if pre_ruff.stdout.strip() else 0
        except Exception:
            pass

    result = _launch_fix_session(finding, system_prompt)

    if not result or not result.get("fixed"):
        error = result.get("error", "unknown") if result else "session_failed"
        log.error("fix_failed", finding_id=finding["id"], error=error)
        files_to_revert = result.get("files_modified", [finding["file_path"]]) if result else [finding["file_path"]]
        _revert_files(files_to_revert)
        _mark_attempted(finding["id"])
        return {"status": "failed", "fixed": False,
                "finding_id": finding["id"], "error": error}

    # Verify the fix independently
    ok, detail = _verify_fix(finding["file_path"], ruff_baseline=ruff_baseline)
    if not ok:
        log.error("fix_verification_failed",
                  finding_id=finding["id"], detail=detail)
        files_to_revert = result.get("files_modified", [finding["file_path"]])
        _revert_files(files_to_revert)
        _mark_attempted(finding["id"])
        return {"status": "verify_failed", "fixed": False,
                "finding_id": finding["id"], "error": detail}

    # Success — mark resolved, leave changes uncommitted for manual review
    _mark_resolved(finding["id"])
    log.info("fix_applied",
             finding_id=finding["id"],
             file_path=finding["file_path"],
             severity=finding["severity"],
             title=finding["title"],
             diff=detail)

    return {
        "status": "ok",
        "fixed": True,
        "finding_id": finding["id"],
        "file_path": finding["file_path"],
        "severity": finding["severity"],
        "title": finding["title"],
        "changes": detail,
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
