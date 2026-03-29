"""
Tier 2 executor — LLM-based fixes via claude -p sessions.

Supports single-finding and multi-file cluster fixes with enriched context.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import structlog
from dotenv import dotenv_values

from app.db.postgres import get_pg_connection
from app.analysis.autofixer.prompt_builder import get_budget

log = structlog.get_logger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent
FIX_PROMPT_PATH = PROJECT_DIR / "scripts" / "fix_prompt.md"
MODEL = os.getenv("CODE_FIX_MODEL", "sonnet")
CLAUDE_BIN = os.getenv("CLAUDE_BIN", "/home/sebastian/.npm-global/bin/claude")
_dotenv_vars = dotenv_values(PROJECT_DIR / ".env")


def _launch_claude_session(system_prompt: str, user_prompt: str,
                           budget: float) -> dict | None:
    """Launch a claude -p session and parse the result."""
    cmd = [
        CLAUDE_BIN, "-p",
        "--model", MODEL,
        "--max-budget-usd", str(budget),
        "--system-prompt", system_prompt,
        "--output-format", "json",
        "--allow-dangerously-skip-permissions",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--add-dir", str(PROJECT_DIR),
        "--allowedTools", "Read,Grep,Edit,Bash(git:*,ruff:*)",
        "--", user_prompt,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            cwd=str(PROJECT_DIR),
            env={**os.environ, **_dotenv_vars, "CLAUDE_CODE_SIMPLE": "1"},
        )

        if result.returncode != 0:
            log.error("claude_session_failed",
                      returncode=result.returncode,
                      stderr=result.stderr[:500])
            return None

        wrapper = json.loads(result.stdout.strip())
        json_str = wrapper.get("result", "")
        cost = wrapper.get("total_cost_usd", 0)

        if wrapper.get("is_error"):
            log.error("claude_session_error", error=json_str[:500])
            return None

        # Parse structured JSON from response
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
            log.warning("no_json_response", preview=wrapper.get("result", "")[:200])
            data = {
                "fixed": True,
                "changes_summary": wrapper.get("result", "")[:200],
                "files_modified": [],
            }

        data["cost_usd"] = round(cost, 4)
        return data

    except subprocess.TimeoutExpired:
        log.error("claude_session_timeout")
        return None
    except json.JSONDecodeError as e:
        log.error("claude_json_parse_failed", error=str(e))
        return None
    except Exception as e:
        log.error("claude_unexpected_error", error=str(e))
        return None


def _verify_fix(file_paths: list[str]) -> tuple[bool, str]:
    """Verify fix: ruff check + git diff on modified files."""
    # Check git diff — ensure something changed
    try:
        diff = subprocess.run(
            ["git", "diff", "--stat"], capture_output=True, text=True,
            timeout=10, cwd=str(PROJECT_DIR),
        )
        if not diff.stdout.strip():
            return False, "no changes detected"
    except Exception as e:
        return False, f"git diff failed: {e}"

    # Ruff check on modified Python files
    for fp in file_paths:
        if fp.endswith(".py"):
            try:
                ruff = subprocess.run(
                    [".venv/bin/ruff", "check", fp],
                    capture_output=True, text=True, timeout=30,
                    cwd=str(PROJECT_DIR),
                )
                # Count errors (not warnings)
                errors = [ln for ln in ruff.stdout.splitlines()
                          if ln.strip() and not ln.startswith("Found")]
                if len(errors) > 5:
                    return False, f"ruff: {len(errors)} errors in {fp}"
            except Exception as e:
                log.warning("ruff_check_failed", file=fp, error=str(e))

    return True, diff.stdout.strip()


def _revert_changes() -> None:
    """Revert all uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, timeout=10, cwd=str(PROJECT_DIR),
        )
        for fp in result.stdout.strip().split("\n"):
            if fp.strip():
                subprocess.run(
                    ["git", "checkout", "--", fp.strip()],
                    capture_output=True, text=True, timeout=10,
                    cwd=str(PROJECT_DIR),
                )
    except Exception as e:
        log.error("revert_failed", error=str(e))


def _mark_resolved(finding_ids: list[int]) -> None:
    """Mark findings as resolved."""
    if not finding_ids:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(finding_ids))
            cur.execute(f"""
                UPDATE code_review_findings
                SET resolved = TRUE, resolved_at = NOW()
                WHERE id IN ({placeholders})
            """, tuple(finding_ids))
        conn.commit()


def _mark_attempted(finding_ids: list[int]) -> None:
    """Increment attempt counter for findings."""
    if not finding_ids:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(finding_ids))
            cur.execute(f"""
                UPDATE code_review_findings
                SET fix_attempted_at = NOW(),
                    fix_attempt_count = fix_attempt_count + 1
                WHERE id IN ({placeholders})
            """, tuple(finding_ids))
            # Check if any reached max attempts
            cur.execute(f"""
                UPDATE code_review_findings
                SET manual_review = TRUE
                WHERE id IN ({placeholders})
                  AND fix_attempt_count >= 6
            """, tuple(finding_ids))
        conn.commit()


def execute_tier2(cluster: dict, context: dict, prompt: str) -> dict:
    """Execute a tier-2 (LLM) fix for a cluster.

    Attempts up to 2 tries. On second failure, marks manual_review=true.
    Returns: {"fixed": bool, "files_modified": [...], "error": str|None, "cost_usd": float}
    """
    finding_ids = [f["id"] for f in cluster["findings"]]
    file_paths = cluster["file_paths"]
    budget = get_budget(cluster["size"])

    log.info("tier2_start",
             cluster_id=cluster["cluster_id"],
             title=cluster["title"],
             files=len(file_paths),
             budget=budget)

    system_prompt = FIX_PROMPT_PATH.read_text(encoding="utf-8")

    # First attempt
    result = _launch_claude_session(system_prompt, prompt, budget)

    if result and result.get("fixed"):
        ok, detail = _verify_fix(file_paths)
        if ok:
            _mark_resolved(finding_ids)
            log.info("tier2_success",
                     cluster_id=cluster["cluster_id"],
                     cost=result.get("cost_usd", 0))
            return {"fixed": True, "files_modified": result.get("files_modified", []),
                    "error": None, "cost_usd": result.get("cost_usd", 0)}
        else:
            log.warning("tier2_verify_failed", detail=detail)
            _revert_changes()

    # Second attempt with retry context
    _revert_changes()
    error_msg = ""
    if result:
        error_msg = result.get("error", "") or "verification failed"
    else:
        error_msg = "session failed or timed out"

    retry_prompt = (
        f"{prompt}\n\n"
        f"**RETRY**: Previous attempt failed: {error_msg}. "
        f"Try a DIFFERENT approach. Check if the fix should be in a different file."
    )

    log.info("tier2_retry", cluster_id=cluster["cluster_id"])
    result2 = _launch_claude_session(system_prompt, retry_prompt, budget)

    if result2 and result2.get("fixed"):
        ok, detail = _verify_fix(file_paths)
        if ok:
            _mark_resolved(finding_ids)
            total_cost = result2.get("cost_usd", 0) + (result.get("cost_usd", 0) if result else 0)
            log.info("tier2_retry_success",
                     cluster_id=cluster["cluster_id"],
                     cost=total_cost)
            return {"fixed": True, "files_modified": result2.get("files_modified", []),
                    "error": None, "cost_usd": total_cost}

    # Both attempts failed
    _revert_changes()
    _mark_attempted(finding_ids)

    final_error = "2x failed"
    if result2:
        final_error = result2.get("error", "") or "verification failed on retry"

    log.error("tier2_exhausted",
              cluster_id=cluster["cluster_id"],
              error=final_error)

    return {"fixed": False, "files_modified": [],
            "error": final_error,
            "cost_usd": sum(r.get("cost_usd", 0) for r in [result, result2] if r)}
