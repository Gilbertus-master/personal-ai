"""
Tier 3 deep fixer — for bugs that tier 2 cannot fix.

Auto-promotes stuck findings (fix_attempt_count >= 3) to manual_review,
then runs a deep research+plan+fix cycle using claude -p with higher budget.

Cron: every 2 hours (only processes 1-2 bugs per run to limit cost).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent
CLAUDE_BIN = os.getenv("CLAUDE_BIN", "/home/sebastian/.npm-global/bin/claude")
MODEL = os.getenv("DEEP_FIX_MODEL", "sonnet")
MAX_BUDGET_PER_BUG = float(os.getenv("DEEP_FIX_BUDGET", "2.0"))
MAX_BUGS_PER_RUN = int(os.getenv("DEEP_FIX_MAX_BUGS", "2"))
MIN_ATTEMPTS_FOR_PROMOTION = 2

_tables_ensured = False


def _ensure_tables():
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE code_review_findings
                ADD COLUMN IF NOT EXISTS tier3_attempted BOOLEAN NOT NULL DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS tier3_attempt_count INTEGER NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS tier3_last_error TEXT
            """)
        conn.commit()
    _tables_ensured = True


def promote_stuck_findings() -> int:
    """Move stuck tier-2 findings (3+ failed attempts) to manual_review."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE code_review_findings
                SET manual_review = TRUE
                WHERE resolved = FALSE
                  AND manual_review = FALSE
                  AND fix_attempt_count >= %s
                RETURNING id
            """, (MIN_ATTEMPTS_FOR_PROMOTION,))
            promoted = cur.fetchall()
        conn.commit()
    count = len(promoted)
    if count:
        log.info("promoted_to_manual_review", count=count)
    return count


def get_deep_fix_candidates() -> list[dict]:
    """Get manual_review findings that haven't been tried by tier 3 yet."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, file_path, category, title, description,
                       suggested_fix, severity, tier3_attempt_count
                FROM code_review_findings
                WHERE manual_review = TRUE
                  AND resolved = FALSE
                  AND tier3_attempted = FALSE
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 99
                    END,
                    CASE category
                        WHEN 'security' THEN 0 WHEN 'correctness' THEN 1
                        WHEN 'optimization' THEN 2 WHEN 'convention' THEN 3
                        ELSE 4
                    END
                LIMIT %s
            """, (MAX_BUGS_PER_RUN,))
            rows = cur.fetchall()
    return [
        {
            "id": r[0], "file_path": r[1], "category": r[2],
            "title": r[3], "description": r[4], "suggested_fix": r[5],
            "severity": r[6], "tier3_attempts": r[7],
        }
        for r in rows
    ]


def _build_deep_prompt(finding: dict) -> tuple[str, str]:
    """Build research+plan+fix prompt for a single finding."""
    system_prompt = """You are a senior Python engineer fixing a bug in the Gilbertus AI system.
Your approach: RESEARCH first, PLAN second, FIX third.

Rules:
- Read the file and surrounding code BEFORE making changes
- Understand WHY the bug exists (root cause, not just symptom)
- Check if similar patterns exist elsewhere that need the same fix
- Make minimal, surgical changes — do NOT refactor unrelated code
- Verify syntax after editing (python -c "import ast; ast.parse(open('FILE').read())")
- If the fix requires changes to multiple files, fix ALL of them

Project conventions (from CLAUDE.md):
- Connection pool (app/db/postgres.py) — always use get_pg_connection()
- Structured logging (structlog) — NEVER print() in production
- Dates ALWAYS absolute (YYYY-MM-DD), timezone: CET (Europe/Warsaw)
- SQL MUST be parameterized (%s placeholders)
- fetchall() instead of fetchone() (psycopg3 convention)
"""

    user_prompt = f"""Fix this bug in /home/sebastian/personal-ai:

**File:** {finding['file_path']}
**Category:** {finding['category']}
**Severity:** {finding['severity']}
**Bug:** {finding['title']}
**Description:** {finding['description']}
**Suggested fix:** {finding.get('suggested_fix', 'none')}

NOTE: The simple autofixer already tried and failed 3+ times on this bug.
You need to do deeper research to understand why the fix is not straightforward.

Steps:
1. Read the file completely
2. Read related files if needed (imports, callers, callees)
3. Understand the root cause
4. Plan the fix (consider edge cases)
5. Apply the fix
6. Verify syntax: python -c "import ast; ast.parse(open('{finding['file_path']}').read())"
7. If you changed multiple files, verify all of them

Output a JSON summary at the end:
```json
{{"fixed": true/false, "files_modified": ["file1.py"], "description": "what was done"}}
```
"""
    return system_prompt, user_prompt


def _run_deep_fix(finding: dict) -> dict:
    """Run deep fix via claude -p with research+plan approach."""
    system_prompt, user_prompt = _build_deep_prompt(finding)

    cmd = [
        CLAUDE_BIN, "-p",
        "--model", MODEL,
        "--max-budget-usd", str(MAX_BUDGET_PER_BUG),
        "--system-prompt", system_prompt,
        "--output-format", "json",
        "--allow-dangerously-skip-permissions",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--add-dir", str(PROJECT_DIR),
        "--allowedTools", "Read,Grep,Glob,Edit,Bash(python:*,git:*,ruff:*)",
        "--", user_prompt,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=900,
            cwd=str(PROJECT_DIR),
            env={**os.environ, "CLAUDE_CODE_SIMPLE": "1"},
        )

        output = result.stdout.strip()
        # Try to parse JSON result from output
        fix_result = _parse_fix_result(output)
        cost = _extract_cost(output)

        return {
            "fixed": fix_result.get("fixed", False),
            "files_modified": fix_result.get("files_modified", []),
            "description": fix_result.get("description", ""),
            "cost_usd": cost,
            "error": None if fix_result.get("fixed") else fix_result.get("description", "unknown"),
        }

    except subprocess.TimeoutExpired:
        return {"fixed": False, "files_modified": [], "cost_usd": MAX_BUDGET_PER_BUG,
                "error": "timeout (900s)"}
    except Exception as e:
        return {"fixed": False, "files_modified": [], "cost_usd": 0,
                "error": str(e)}


def _parse_fix_result(output: str) -> dict:
    """Extract JSON result from claude output."""
    # Look for JSON block in output
    for line in reversed(output.split("\n")):
        line = line.strip()
        if line.startswith("{") and "fixed" in line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    # Try to find in code blocks
    import re
    json_blocks = re.findall(r'```json\s*\n(.*?)\n```', output, re.DOTALL)
    for block in reversed(json_blocks):
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue
    return {"fixed": False, "description": "could not parse result"}


def _extract_cost(output: str) -> float:
    """Extract cost from claude output."""
    import re
    for line in output.split("\n"):
        m = re.search(r'"cost_usd":\s*([\d.]+)', line)
        if m:
            return float(m.group(1))
    return 0.0


def _update_finding(finding_id: int, result: dict) -> None:
    """Update finding in DB after deep fix attempt."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if result.get("fixed"):
                cur.execute("""
                    UPDATE code_review_findings
                    SET resolved = TRUE, resolved_at = NOW(),
                        tier3_attempted = TRUE,
                        tier3_attempt_count = tier3_attempt_count + 1
                    WHERE id = %s
                """, (finding_id,))
            else:
                cur.execute("""
                    UPDATE code_review_findings
                    SET tier3_attempted = TRUE,
                        tier3_attempt_count = tier3_attempt_count + 1,
                        tier3_last_error = %s
                    WHERE id = %s
                """, (result.get("error", "unknown"), finding_id))
        conn.commit()


def run_deep_fix_cycle() -> list[dict]:
    """Main entry: promote stuck → pick candidates → deep fix."""
    _ensure_tables()

    # Step 1: Promote stuck tier-2 findings
    promoted = promote_stuck_findings()

    # Step 2: Get candidates for deep fix
    candidates = get_deep_fix_candidates()
    if not candidates:
        log.info("no_deep_fix_candidates")
        return []

    log.info("deep_fix_start", candidates=len(candidates), promoted=promoted)

    results = []
    for finding in candidates:
        log.info("deep_fix_attempt",
                 id=finding["id"],
                 category=finding["category"],
                 title=finding["title"][:60],
                 file=finding["file_path"])

        result = _run_deep_fix(finding)
        result["finding_id"] = finding["id"]
        result["title"] = finding["title"]
        result["category"] = finding["category"]

        _update_finding(finding["id"], result)
        results.append(result)

        log.info("deep_fix_result",
                 id=finding["id"],
                 fixed=result.get("fixed", False),
                 cost=result.get("cost_usd", 0),
                 files=result.get("files_modified", []))

    fixed = sum(1 for r in results if r.get("fixed"))
    log.info("deep_fix_complete", total=len(results), fixed=fixed)
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tier 3 deep fixer")
    parser.add_argument("--dry-run", action="store_true", help="Show candidates without fixing")
    parser.add_argument("--max-bugs", type=int, default=MAX_BUGS_PER_RUN)
    args = parser.parse_args()

    if args.dry_run:
        _ensure_tables()
        promote_stuck_findings()
        candidates = get_deep_fix_candidates()
        for c in candidates:
            print(json.dumps(c, ensure_ascii=False, indent=2, default=str))
        print(f"\n{len(candidates)} candidates for deep fix")
    else:
        MAX_BUGS_PER_RUN = args.max_bugs
        results = run_deep_fix_cycle()
        for r in results:
            print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
