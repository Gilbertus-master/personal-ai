"""
Context gatherer — enriches clusters with file contents, resolved examples, and conventions.
"""
from __future__ import annotations

from pathlib import Path

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent

PROJECT_CONVENTIONS = """
## Project Conventions (MUST follow)
- SQL MUST be parameterized — use %s placeholders with params tuple, NEVER f-strings for values
- DB connections MUST use `get_pg_connection()` from `app/db/postgres.py` — NEVER raw psycopg connect
- Structured logging via `structlog` — NEVER `print()` in production code (log = structlog.get_logger(__name__))
- All external API calls need explicit timeouts
- Use `fetchall()` + check `len(rows)` instead of `fetchone()` in psycopg3
- API cost tracking: every Anthropic API call should use `log_anthropic_cost()`
- Use prompt caching (`cache_control: {"type": "ephemeral"}`) on system prompts
- Connection pool is in `app/db/postgres.py` — always import from there
""".strip()


def _read_file_context(file_path: str, line_start: int | None, line_end: int | None,
                       context_lines: int = 20) -> str:
    """Read ±context_lines around the finding location."""
    abs_path = PROJECT_DIR / file_path
    if not abs_path.exists():
        return f"# File not found: {file_path}"

    try:
        lines = abs_path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        return f"# Error reading {file_path}: {e}"

    if line_start is None:
        # No line info — return first 60 lines
        return "\n".join(f"{i+1}: {ln}" for i, ln in enumerate(lines[:60]))

    start = max(0, line_start - 1 - context_lines)
    end_line = (line_end or line_start) + context_lines
    snippet = lines[start:end_line]
    return "\n".join(f"{start+i+1}: {ln}" for i, ln in enumerate(snippet))


def _get_resolved_similar(category: str, title: str, limit: int = 3) -> list[dict]:
    """Find resolved findings with the same category and similar title."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # First try exact match
            cur.execute("""
                SELECT id, file_path, title, description, suggested_fix
                FROM code_review_findings
                WHERE resolved = TRUE AND category = %s AND title = %s
                ORDER BY resolved_at DESC
                LIMIT %s
            """, (category, title, limit))
            rows = cur.fetchall()

            # If no exact match, try category-level
            if not rows:
                cur.execute("""
                    SELECT id, file_path, title, description, suggested_fix
                    FROM code_review_findings
                    WHERE resolved = TRUE AND category = %s
                    ORDER BY resolved_at DESC
                    LIMIT %s
                """, (category, limit))
                rows = cur.fetchall()

    return [
        {
            "id": r[0], "file_path": r[1], "title": r[2],
            "description": r[3], "suggested_fix": r[4],
        }
        for r in rows
    ]


def gather_cluster_context(cluster: dict) -> dict:
    """Gather all context needed for a cluster fix.

    Returns dict with file_contents, resolved_similar, project_conventions, cluster_size.
    """
    file_contents: dict[str, str] = {}
    for finding in cluster["findings"]:
        fp = finding["file_path"]
        if fp not in file_contents:
            file_contents[fp] = _read_file_context(
                fp, finding["line_start"], finding["line_end"]
            )

    resolved = _get_resolved_similar(cluster["category"], cluster["title"])

    context = {
        "file_contents": file_contents,
        "resolved_similar": resolved,
        "project_conventions": PROJECT_CONVENTIONS,
        "cluster_size": cluster["size"],
    }

    log.info("context_gathered",
             cluster_id=cluster["cluster_id"],
             files=len(file_contents),
             resolved_examples=len(resolved))

    return context
