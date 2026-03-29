"""
Tier 1 executor — deterministic fixes without LLM.

Handles: unused imports (F401), unused variables (F811), print→structlog.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _run_cmd(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command and return result."""
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, cwd=str(PROJECT_DIR)
    )


def _fix_unused_imports(file_paths: list[str]) -> tuple[list[str], str | None]:
    """Fix unused imports via ruff --fix."""
    fixed_files = []
    for fp in file_paths:
        abs_path = PROJECT_DIR / fp
        if not abs_path.exists():
            continue

        try:
            _run_cmd([
                ".venv/bin/ruff", "check", "--select", "F401,F811", "--fix", fp
            ])
            # Check if file was actually modified
            diff = _run_cmd(["git", "diff", "--stat", fp])
            if diff.stdout.strip():
                fixed_files.append(fp)
        except subprocess.TimeoutExpired:
            return fixed_files, f"ruff timeout on {fp}"
        except Exception as e:
            return fixed_files, str(e)

    return fixed_files, None


def _fix_print_to_structlog(file_paths: list[str]) -> tuple[list[str], str | None]:
    """Replace print() with structlog in production files.

    Only replaces in files that already import structlog or are under app/.
    Skips files that use print() for CLI output (scripts with __main__).
    """
    fixed_files = []
    for fp in file_paths:
        abs_path = PROJECT_DIR / fp
        if not abs_path.exists():
            continue
        if not fp.startswith("app/"):
            continue

        try:
            content = abs_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Skip if it's a CLI script with __main__
        if "if __name__" in content:
            continue

        # Ensure structlog import exists
        has_structlog = "import structlog" in content
        has_print = re.search(r"\bprint\(", content)

        if not has_print:
            continue

        lines = content.splitlines()
        new_lines = []
        modified = False

        # Add structlog import if not present
        if not has_structlog:
            # Find first non-comment, non-import line after __future__
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.startswith("from __future__"):
                    insert_idx = i + 1
                    break
            if insert_idx == 0:
                for i, line in enumerate(lines):
                    if line.startswith("import ") or line.startswith("from "):
                        insert_idx = i
                        break

            lines.insert(insert_idx, "import structlog")
            lines.insert(insert_idx + 1, 'log = structlog.get_logger(__name__)')
            lines.insert(insert_idx + 2, "")

        for line in lines:
            stripped = line.lstrip()
            indent = line[:len(line) - len(stripped)]

            # Simple print() → log.info()
            if re.match(r'print\(f?"', stripped) or re.match(r"print\(f?'", stripped):
                # Extract the content
                match = re.match(r'print\((.*)\)\s*$', stripped)
                if match:
                    arg = match.group(1)
                    # Convert f-string to structlog kwargs if simple
                    new_lines.append(f"{indent}log.info({arg})")
                    modified = True
                    continue
            elif re.match(r'print\(', stripped):
                match = re.match(r'print\((.*)\)\s*$', stripped)
                if match:
                    arg = match.group(1)
                    new_lines.append(f"{indent}log.info({arg})")
                    modified = True
                    continue

            new_lines.append(line)

        if modified:
            abs_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            # Verify with ruff
            verify = _run_cmd([".venv/bin/ruff", "check", fp])
            if verify.returncode != 0 and "error" in verify.stdout.lower():
                # Revert
                _run_cmd(["git", "checkout", "--", fp])
                log.warning("tier1_print_revert", file=fp, reason=verify.stdout[:200])
            else:
                fixed_files.append(fp)

    return fixed_files, None


def _verify_imports(file_paths: list[str]) -> tuple[bool, str]:
    """Verify modified files are importable."""
    for fp in file_paths:
        if not fp.endswith(".py"):
            continue
        module = fp.replace("/", ".").replace(".py", "")
        try:
            result = _run_cmd(["python3", "-c", f"import {module}"], timeout=15)
            if result.returncode != 0:
                return False, f"Import failed for {module}: {result.stderr[:200]}"
        except subprocess.TimeoutExpired:
            return False, f"Import timeout for {module}"
    return True, ""


def _mark_resolved(finding_ids: list[int]) -> None:
    """Mark multiple findings as resolved."""
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
    """Mark multiple findings as attempted."""
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
        conn.commit()


def execute_tier1(cluster: dict) -> dict:
    """Execute a tier-1 (deterministic) fix for a cluster.

    Returns: {"fixed": bool, "files_modified": [...], "error": str|None}
    """
    title_lower = cluster["title"].lower()
    file_paths = cluster["file_paths"]
    finding_ids = [f["id"] for f in cluster["findings"]]

    log.info("tier1_start",
             cluster_id=cluster["cluster_id"],
             title=cluster["title"],
             files=len(file_paths))

    fixed_files: list[str] = []
    error: str | None = None

    if "unused" in title_lower and ("import" in title_lower or "variable" in title_lower):
        fixed_files, error = _fix_unused_imports(file_paths)
    elif "print" in title_lower or "structlog" in title_lower:
        fixed_files, error = _fix_print_to_structlog(file_paths)
    else:
        error = f"No tier-1 strategy for: {cluster['title']}"
        _mark_attempted(finding_ids)
        return {"fixed": False, "files_modified": [], "error": error}

    if error:
        _mark_attempted(finding_ids)
        return {"fixed": False, "files_modified": fixed_files, "error": error}

    if not fixed_files:
        _mark_attempted(finding_ids)
        return {"fixed": False, "files_modified": [],
                "error": "No files were modified by tier-1 fix"}

    # Verify
    ok, detail = _verify_imports(fixed_files)
    if not ok:
        # Revert all
        for fp in fixed_files:
            _run_cmd(["git", "checkout", "--", fp])
        _mark_attempted(finding_ids)
        return {"fixed": False, "files_modified": [], "error": detail}

    _mark_resolved(finding_ids)
    log.info("tier1_success",
             cluster_id=cluster["cluster_id"],
             fixed_files=fixed_files)

    return {"fixed": True, "files_modified": fixed_files, "error": None}
