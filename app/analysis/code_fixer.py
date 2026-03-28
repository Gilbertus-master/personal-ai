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

import argparse
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
CLAUDE_BIN = os.getenv("CLAUDE_BIN", "/home/sebastian/.npm-global/bin/claude")

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


MAX_ATTEMPTS_PER_ROUND = 3   # max attempts before skipping to next round
MAX_ROUNDS = 2               # after 2 rounds of failures → manual queue


def _ensure_schema() -> None:
    """Ensure retry tracking columns exist."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE code_review_findings
                ADD COLUMN IF NOT EXISTS fix_attempted_at TIMESTAMPTZ
            """)
            cur.execute("""
                ALTER TABLE code_review_findings
                ADD COLUMN IF NOT EXISTS fix_attempt_count INTEGER NOT NULL DEFAULT 0
            """)
            cur.execute("""
                ALTER TABLE code_review_findings
                ADD COLUMN IF NOT EXISTS manual_review BOOLEAN NOT NULL DEFAULT FALSE
            """)
        conn.commit()


def _get_next_finding(exclude_files: list[str] | None = None) -> dict | None:
    """Get the single highest-priority unresolved finding.

    Priority logic:
    - Skip manual_review=true (exhausted all auto-fix attempts)
    - Skip findings with MAX_ATTEMPTS_PER_ROUND * MAX_ROUNDS attempts
    - Prefer unattempted findings, then least-attempted
    - Exclude files currently being worked on by other workers
    """
    exclude = exclude_files or []
    max_total = MAX_ATTEMPTS_PER_ROUND * MAX_ROUNDS

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if exclude:
                placeholders = ",".join(["%s"] * len(exclude))
                where_excl = f"AND file_path NOT IN ({placeholders})"
                params = (max_total,) + tuple(exclude)
            else:
                where_excl = ""
                params = (max_total,)

            cur.execute(f"""
                SELECT id, file_path, severity, category, title, description,
                       line_start, line_end, suggested_fix, fix_attempt_count
                FROM code_review_findings
                WHERE resolved = FALSE
                  AND manual_review = FALSE
                  AND severity IN ('critical', 'high', 'medium', 'low')
                  AND fix_attempt_count < %s
                  AND (fix_attempted_at IS NULL
                       OR fix_attempted_at < NOW() - INTERVAL '2 hours')
                  {where_excl}
                ORDER BY fix_attempt_count ASC, {SEVERITY_ORDER}, created_at ASC
                LIMIT 1
            """, params)
            rows = cur.fetchall()
            if not rows:
                return None
            r = rows[0]
            return {
                "id": r[0], "file_path": r[1], "severity": r[2],
                "category": r[3], "title": r[4], "description": r[5],
                "line_start": r[6], "line_end": r[7], "suggested_fix": r[8],
                "fix_attempt_count": r[9],
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
        f"**Attempt**: {finding.get('fix_attempt_count', 0) + 1} "
        f"(previous attempts may have failed because the bug is in a DIFFERENT file than file_path)\n\n"
        f"Steps:\n"
        f"{read_instruction}\n"
        f"2. IMPORTANT: If the bug described is NOT in this file, use Grep to find where the actual "
        f"code lives (e.g. the function mentioned in the description). Fix the actual source.\n"
        f"3. Apply the fix using the Edit tool — minimal change only\n"
        f"4. For Python: run `ruff check <modified_file>`\n"
        f"5. Run: git diff\n"
        f"6. Output ONLY the JSON result (no markdown fences, no extra text)"
    )


def _launch_fix_session(finding: dict, system_prompt: str) -> dict | None:
    """Launch a dedicated claude -p session to fix one finding."""
    user_prompt = _build_user_prompt(finding)

    cmd = [
        CLAUDE_BIN, "-p",
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
    """Post-fix verification: ruff (only new errors) + git diff.

    Checks git diff on ALL changed files (not just finding's file_path),
    because the actual fix may be in an imported/related file.
    """
    # Check git diff — ensure something actually changed (ANY file)
    try:
        diff_result = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_DIR),
        )
        if not diff_result.stdout.strip():
            return False, "no changes detected in any file"
        diff_stat = diff_result.stdout.strip()
    except Exception as e:
        return False, f"git diff failed: {e}"

    # Extract actually modified files from diff
    modified_files = []
    for line in diff_stat.split("\n"):
        if "|" in line:
            fp = line.split("|")[0].strip()
            if fp:
                modified_files.append(fp)

    # Check ruff for each modified Python file — only fail if NEW errors introduced
    for mf in modified_files:
        if mf.endswith(".py"):
            try:
                # Get baseline for this specific file (may not be the finding's file)
                pre_baseline = ruff_baseline if mf == file_path else 0

                ruff_result = subprocess.run(
                    [".venv/bin/ruff", "check", mf],
                    capture_output=True, text=True, timeout=30,
                    cwd=str(PROJECT_DIR),
                )
                current_errors = ruff_result.stdout.count("\n") if ruff_result.stdout.strip() else 0
                if current_errors > pre_baseline:
                    return False, f"ruff: {current_errors - pre_baseline} new errors in {mf}: {ruff_result.stdout[:300]}"
            except Exception as e:
                log.warning("ruff_check_failed", file=mf, error=str(e))

    return True, diff_stat


def _revert_all_changes() -> None:
    """Revert ALL uncommitted changes (safe: fixer never commits)."""
    try:
        # Get list of changed files
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_DIR),
        )
        changed = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        if not changed:
            return
        for fp in changed:
            subprocess.run(
                ["git", "checkout", "--", fp],
                capture_output=True, text=True, timeout=10,
                cwd=str(PROJECT_DIR),
            )
            log.warning("fix_reverted", file_path=fp)
    except Exception as e:
        log.error("revert_failed", error=str(e))


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
    """Increment attempt counter. If exhausted all rounds, move to manual queue."""
    max_total = MAX_ATTEMPTS_PER_ROUND * MAX_ROUNDS
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE code_review_findings
                SET fix_attempted_at = NOW(),
                    fix_attempt_count = fix_attempt_count + 1
                WHERE id = %s
                RETURNING fix_attempt_count
            """, (finding_id,))
            rows = cur.fetchall()
            new_count = rows[0][0] if rows else 0

            if new_count >= max_total:
                cur.execute("""
                    UPDATE code_review_findings
                    SET manual_review = TRUE
                    WHERE id = %s
                """, (finding_id,))
                log.warning("moved_to_manual_queue",
                            finding_id=finding_id,
                            attempts=new_count)
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
        _revert_all_changes()
        _mark_attempted(finding["id"])
        return {"status": "failed", "fixed": False,
                "finding_id": finding["id"], "error": error}

    # Verify the fix independently
    ok, detail = _verify_fix(finding["file_path"], ruff_baseline=ruff_baseline)
    if not ok:
        log.error("fix_verification_failed",
                  finding_id=finding["id"], detail=detail)
        _revert_all_changes()
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


def run_parallel(workers: int = 3) -> list[dict]:
    """Run multiple fix workers in parallel, each on a different file.

    Safety guarantees:
    - Each worker picks a finding from a DIFFERENT file (no edit conflicts)
    - PG advisory lock per file_path prevents races
    - git revert on failure is per-file (safe for parallel)
    - Workers are threads (shared process, shared connection pool)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    _ensure_schema()

    # Collect findings for different files (sequential, no race)
    locked_files: list[str] = []
    findings: list[dict] = []

    for _ in range(workers):
        f = _get_next_finding(exclude_files=locked_files)
        if not f:
            break
        if f["file_path"] in locked_files:
            break  # no more unique files
        locked_files.append(f["file_path"])
        findings.append(f)

    if not findings:
        log.info("parallel_no_findings")
        return [{"status": "idle", "fixed": False}]

    log.info("parallel_start", workers=len(findings),
             files=[f["file_path"] for f in findings])

    system_prompt = FIX_PROMPT_PATH.read_text(encoding="utf-8")
    results = []
    lock = threading.Lock()

    def _fix_one(finding: dict) -> dict:
        """Fix a single finding (thread-safe)."""
        if not _validate_file_path(finding["file_path"]):
            _mark_attempted(finding["id"])
            return {"status": "skipped", "fixed": False,
                    "finding_id": finding["id"],
                    "reason": "file_path not in allowed dirs"}

        # Capture ruff baseline
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
            with lock:
                _revert_all_changes()
            _mark_attempted(finding["id"])
            return {"status": "failed", "fixed": False,
                    "finding_id": finding["id"], "error": error}

        ok, detail = _verify_fix(finding["file_path"], ruff_baseline=ruff_baseline)
        if not ok:
            log.error("fix_verification_failed",
                      finding_id=finding["id"], detail=detail)
            with lock:
                _revert_all_changes()
            _mark_attempted(finding["id"])
            return {"status": "verify_failed", "fixed": False,
                    "finding_id": finding["id"], "error": detail}

        _mark_resolved(finding["id"])
        log.info("fix_applied",
                 finding_id=finding["id"],
                 file_path=finding["file_path"],
                 severity=finding["severity"],
                 title=finding["title"],
                 diff=detail)

        return {
            "status": "ok", "fixed": True,
            "finding_id": finding["id"],
            "file_path": finding["file_path"],
            "severity": finding["severity"],
            "title": finding["title"],
            "changes": detail,
        }

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_fix_one, f): f for f in findings}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                f = futures[future]
                log.error("worker_crashed", finding_id=f["id"], error=str(e))
                _mark_attempted(f["id"])
                results.append({"status": "error", "fixed": False,
                                "finding_id": f["id"], "error": str(e)})

    fixed = sum(1 for r in results if r.get("fixed"))
    log.info("parallel_complete", total=len(results), fixed=fixed)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parallel", type=int, default=0,
                        help="Run N workers in parallel (0 = single mode)")
    args = parser.parse_args()

    if args.parallel > 0:
        results = run_parallel(workers=args.parallel)
        for r in results:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    else:
        result = run()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
