"""
Automated code review orchestrator — one Claude Code session per file.

Iterates through all project source files, launching a dedicated `claude -p`
session for each. Each session gets full agent capabilities (Read, Grep, Bash)
to deeply analyze the file, its imports, callers, and git history.

Findings are stored in DB tables for tracking, resolution, and daily digest.

Cron: every 30 min, 5 files per run.
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
_dotenv_vars = dotenv_values(PROJECT_DIR / ".env")
REVIEW_PROMPT_PATH = PROJECT_DIR / "scripts" / "review_prompt.md"
MODEL = os.getenv("CODE_REVIEW_MODEL", "sonnet")
BUDGET_PER_FILE = float(os.getenv("CODE_REVIEW_BUDGET_PER_FILE", "0.50"))
REVIEW_BATCH_DEFAULT = 5
RE_REVIEW_DAYS = 30

# Directories and patterns to scan
SCAN_PATTERNS = [
    ("app", "**/*.py"),
    ("scripts", "*.sh"),
    ("scripts", "*.py"),
    ("mcp_gilbertus", "*.py"),
]

# Files/dirs to skip
SKIP_PATTERNS = {
    "__pycache__", ".pyc", "__init__.py", "node_modules", ".venv",
}


def _ensure_tables() -> None:
    """Create review tables if they don't exist."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS code_review_files (
                    id BIGSERIAL PRIMARY KEY,
                    file_path TEXT NOT NULL UNIQUE,
                    file_hash TEXT,
                    language TEXT,
                    last_reviewed_at TIMESTAMPTZ,
                    review_count INTEGER DEFAULT 0,
                    overall_quality TEXT,
                    last_git_modified TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS code_review_findings (
                    id BIGSERIAL PRIMARY KEY,
                    file_id BIGINT REFERENCES code_review_files(id),
                    file_path TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    line_start INTEGER,
                    line_end INTEGER,
                    suggested_fix TEXT,
                    model_used TEXT,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_crf_severity
                ON code_review_findings(severity)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_crf_unresolved
                ON code_review_findings(resolved, severity)
            """)
        conn.commit()
    log.info("code_review_tables_ensured")


def _file_hash(path: Path) -> str:
    """SHA256 of file content."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _git_modified_date(path: Path) -> datetime | None:
    """Get last git modification date for a file."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            capture_output=True, text=True, timeout=10,
            cwd=PROJECT_DIR,
        )
        if result.stdout.strip():
            return datetime.fromisoformat(result.stdout.strip())
    except Exception:
        pass
    return None


def _scan_project_files() -> list[dict]:
    """Scan project for all reviewable source files."""
    files = []
    for base_dir, pattern in SCAN_PATTERNS:
        base = PROJECT_DIR / base_dir
        if not base.exists():
            continue
        for path in base.glob(pattern):
            if any(skip in str(path) for skip in SKIP_PATTERNS):
                continue
            if not path.is_file():
                continue
            rel = str(path.relative_to(PROJECT_DIR))
            lang = "python" if path.suffix == ".py" else "bash"
            files.append({
                "file_path": rel,
                "abs_path": path,
                "language": lang,
            })
    return files


def _sync_file_inventory() -> int:
    """Sync discovered files into code_review_files table. Returns count."""
    files = _scan_project_files()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for f in files:
                git_mod = _git_modified_date(f["abs_path"])
                cur.execute("""
                    INSERT INTO code_review_files (file_path, language, last_git_modified)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (file_path) DO UPDATE SET
                        language = EXCLUDED.language,
                        last_git_modified = COALESCE(EXCLUDED.last_git_modified, code_review_files.last_git_modified)
                """, (f["file_path"], f["language"], git_mod))
        conn.commit()
    log.info("file_inventory_synced", count=len(files))
    return len(files)


def _get_next_files(limit: int) -> list[dict]:
    """Get next files to review, prioritized."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, file_path, file_hash, language
                FROM code_review_files
                WHERE last_reviewed_at IS NULL
                ORDER BY last_git_modified DESC NULLS LAST
                LIMIT %s
            """, (limit,))
            never_reviewed = [
                {"id": r[0], "file_path": r[1], "old_hash": r[2], "language": r[3]}
                for r in cur.fetchall()
            ]
            if len(never_reviewed) >= limit:
                return never_reviewed

            remaining = limit - len(never_reviewed)

            # Files changed since last review
            cur.execute("""
                SELECT id, file_path, file_hash, language
                FROM code_review_files
                WHERE last_reviewed_at IS NOT NULL
                ORDER BY last_reviewed_at ASC
                LIMIT %s
            """, (remaining,))
            oldest = [
                {"id": r[0], "file_path": r[1], "old_hash": r[2], "language": r[3]}
                for r in cur.fetchall()
            ]

            return never_reviewed + oldest


def _get_lessons_learned() -> str:
    """Fetch lessons from DB for injection into review prompt."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT category, description, prevention_rule
                    FROM lessons_learned ORDER BY id
                """)
                rows = cur.fetchall()
                if not rows:
                    return "No lessons learned yet."
                lines = []
                for i, (cat, desc, rule) in enumerate(rows, 1):
                    lines.append(f"{i}. [{cat}] {desc}\n   Prevention: {rule}")
                return "\n".join(lines)
    except Exception:
        return "Could not load lessons learned."


def _build_system_prompt() -> str:
    """Build full system prompt with lessons learned injected."""
    template = REVIEW_PROMPT_PATH.read_text(encoding="utf-8")
    lessons = _get_lessons_learned()
    return template.replace("{LESSONS_LEARNED}", lessons)


def _launch_review_session(file_path: str, system_prompt: str) -> dict | None:
    """Launch a dedicated claude -p session for one file. Returns parsed JSON or None."""
    abs_path = PROJECT_DIR / file_path

    if not abs_path.exists():
        log.warning("file_not_found", file_path=file_path)
        return None

    # Write system prompt to temp file (with lessons learned injected)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", prefix="review_prompt_",
        delete=False, encoding="utf-8",
    ) as tmp:
        tmp.write(system_prompt)
        prompt_file = tmp.name

    user_prompt = (
        f"Review the file: {file_path}\n\n"
        f"Steps:\n"
        f"1. Read the file with the Read tool\n"
        f"2. Check its imports and any closely related files\n"
        f"3. Run: git log --oneline -5 -- {file_path}\n"
        f"4. Analyze for all review dimensions\n"
        f"5. Output ONLY the JSON result (no markdown fences, no extra text)"
    )

    cmd = [
        "claude", "-p",
        "--bare",
        "--model", MODEL,
        "--max-budget-usd", str(BUDGET_PER_FILE),
        "--system-prompt-file", prompt_file,
        "--output-format", "json",
        "--allow-dangerously-skip-permissions",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--add-dir", str(PROJECT_DIR),
        "--allowedTools", "Read,Grep,Bash(git:*)",
        "--", user_prompt,
    ]

    log.info("launching_review", file_path=file_path, model=MODEL)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max per file
            cwd=str(PROJECT_DIR),
            env={**os.environ, **_dotenv_vars, "CLAUDE_CODE_SIMPLE": "1"},
        )

        raw_output = result.stdout.strip()

        if result.returncode != 0:
            log.error("review_session_failed",
                      file_path=file_path,
                      returncode=result.returncode,
                      stderr=result.stderr[:500])
            return None

        # --output-format json wraps response in {"result": "...", ...}
        wrapper = json.loads(raw_output)
        cost = wrapper.get("total_cost_usd", 0)
        json_str = wrapper.get("result", "")

        if wrapper.get("is_error"):
            log.error("review_session_error",
                      file_path=file_path,
                      error=json_str[:500])
            return None

        # Parse the actual review JSON from the result field
        # Handle markdown fences if present
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        # Find JSON object
        start = json_str.find("{")
        end = json_str.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = json_str[start:end]

        data = json.loads(json_str)
        log.info("review_completed",
                 file_path=file_path,
                 quality=data.get("overall_quality"),
                 findings=len(data.get("findings", [])),
                 cost_usd=round(cost, 4))
        return data

    except subprocess.TimeoutExpired:
        log.error("review_timeout", file_path=file_path)
        return None
    except json.JSONDecodeError as e:
        log.error("review_json_parse_failed",
                  file_path=file_path,
                  error=str(e),
                  raw_output=raw_output[:500] if raw_output else "empty")
        return None
    except Exception as e:
        log.error("review_unexpected_error", file_path=file_path, error=str(e))
        return None
    finally:
        try:
            os.unlink(prompt_file)
        except OSError:
            pass


def _save_findings(file_info: dict, review_data: dict) -> int:
    """Save review results to DB. Returns number of findings saved."""
    file_id = file_info["id"]
    file_path = file_info["file_path"]
    abs_path = PROJECT_DIR / file_path

    current_hash = _file_hash(abs_path) if abs_path.exists() else None
    overall = review_data.get("overall_quality", "unknown")
    findings = review_data.get("findings", [])

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Update file review state
            cur.execute("""
                UPDATE code_review_files
                SET file_hash = %s,
                    last_reviewed_at = NOW(),
                    review_count = review_count + 1,
                    overall_quality = %s
                WHERE id = %s
            """, (current_hash, overall, file_id))

            # Save each finding
            for f in findings:
                cur.execute("""
                    INSERT INTO code_review_findings
                    (file_id, file_path, severity, category, title, description,
                     line_start, line_end, suggested_fix, model_used)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    file_id,
                    file_path,
                    f.get("severity", "info"),
                    f.get("category", "quality"),
                    f.get("title", "Untitled finding"),
                    f.get("description", ""),
                    f.get("line_start"),
                    f.get("line_end"),
                    f.get("suggested_fix"),
                    MODEL,
                ))
        conn.commit()

    log.info("findings_saved", file_path=file_path, count=len(findings), quality=overall)
    return len(findings)


def _mark_file_reviewed_no_findings(file_info: dict) -> None:
    """Mark file as reviewed even if session failed (to avoid infinite retry)."""
    abs_path = PROJECT_DIR / file_info["file_path"]
    current_hash = _file_hash(abs_path) if abs_path.exists() else None

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE code_review_files
                SET file_hash = %s,
                    last_reviewed_at = NOW(),
                    review_count = review_count + 1,
                    overall_quality = 'error'
                WHERE id = %s
            """, (current_hash, file_info["id"]))
        conn.commit()


def run(batch_size: int = REVIEW_BATCH_DEFAULT) -> dict:
    """Main entry: sync inventory, pick files, review each, save findings."""
    _ensure_tables()
    total_files = _sync_file_inventory()

    files = _get_next_files(batch_size)
    if not files:
        log.info("no_files_to_review")
        return {"status": "idle", "reviewed": 0, "findings": 0, "total_files": total_files}

    system_prompt = _build_system_prompt()

    reviewed = 0
    total_findings = 0

    for file_info in files:
        # Check if file still exists
        abs_path = PROJECT_DIR / file_info["file_path"]
        if not abs_path.exists():
            log.warning("file_disappeared", file_path=file_info["file_path"])
            _mark_file_reviewed_no_findings(file_info)
            continue

        # Check if file changed since last review (skip unchanged in re-review cycle)
        current_hash = _file_hash(abs_path)
        if file_info["old_hash"] == current_hash:
            # File unchanged — still mark as reviewed to cycle through
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE code_review_files
                        SET last_reviewed_at = NOW()
                        WHERE id = %s
                    """, (file_info["id"],))
                conn.commit()
            log.info("file_unchanged_skipped", file_path=file_info["file_path"])
            continue

        review_data = _launch_review_session(file_info["file_path"], system_prompt)

        if review_data:
            count = _save_findings(file_info, review_data)
            total_findings += count
        else:
            _mark_file_reviewed_no_findings(file_info)

        reviewed += 1

    return {
        "status": "ok",
        "reviewed": reviewed,
        "findings": total_findings,
        "total_files": total_files,
    }


def get_summary(days: int = 1) -> str | None:
    """Generate WhatsApp-friendly summary of recent findings."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT severity, COUNT(*) as cnt
                FROM code_review_findings
                WHERE created_at > NOW() - INTERVAL '%s days'
                  AND resolved = FALSE
                GROUP BY severity
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END
            """, (days,))
            severity_counts = cur.fetchall()

            if not severity_counts:
                return None

            cur.execute("""
                SELECT f.file_path, f.severity, f.category, f.title
                FROM code_review_findings f
                WHERE f.created_at > NOW() - INTERVAL '%s days'
                  AND f.resolved = FALSE
                  AND f.severity IN ('critical', 'high')
                ORDER BY
                    CASE f.severity WHEN 'critical' THEN 0 ELSE 1 END,
                    f.created_at DESC
                LIMIT 10
            """, (days,))
            critical_findings = cur.fetchall()

            cur.execute("""
                SELECT COUNT(DISTINCT file_path)
                FROM code_review_findings
                WHERE created_at > NOW() - INTERVAL '%s days'
            """, (days,))
            files_reviewed = cur.fetchall()[0][0]

    lines = [f"Code Review ({days}d): {files_reviewed} files"]
    for sev, cnt in severity_counts:
        lines.append(f"  {sev}: {cnt}")

    if critical_findings:
        lines.append("\nTop issues:")
        for fp, sev, cat, title in critical_findings:
            short_path = fp.split("/")[-1]
            lines.append(f"  [{sev}] {short_path}: {title}")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated code reviewer")
    parser.add_argument("--batch", type=int, default=REVIEW_BATCH_DEFAULT,
                        help="Number of files to review per run")
    args = parser.parse_args()

    result = run(batch_size=args.batch)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
