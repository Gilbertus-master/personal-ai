"""
Tier 1 executor — deterministic fixes without LLM.

Handles: unused imports (F401), unused variables (F811/F841),
print→structlog, date format in shell, dead code.
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
            diff = _run_cmd(["git", "diff", "--stat", fp])
            if diff.stdout.strip():
                fixed_files.append(fp)
        except subprocess.TimeoutExpired:
            return fixed_files, f"ruff timeout on {fp}"
        except Exception as e:
            return fixed_files, str(e)

    return fixed_files, None


def _fix_print_to_structlog(file_paths: list[str]) -> tuple[list[str], str | None]:
    """Replace print() with structlog in production Python files.

    Handles app/ and scripts/ directories. Skips print() inside
    `if __name__ == "__main__"` blocks (CLI output).
    """
    fixed_files = []
    for fp in file_paths:
        abs_path = PROJECT_DIR / fp
        if not abs_path.exists() or not fp.endswith(".py"):
            continue

        try:
            content = abs_path.read_text(encoding="utf-8")
        except Exception:
            continue

        has_print = re.search(r"\bprint\(", content)
        if not has_print:
            continue

        lines = content.splitlines()
        new_lines = []
        modified = False
        in_main_block = False
        main_indent = 0

        # Ensure structlog import and logger exist without creating E402 violations.
        # Strategy:
        #   1. Insert `import structlog` in the imports block (after __future__, before code)
        #   2. Insert `log = structlog.get_logger(__name__)` AFTER the last import line
        has_structlog = "import structlog" in content
        has_log_var = re.search(r'^log\s*=\s*structlog', content, re.MULTILINE)
        if not has_structlog or not has_log_var:
            # Find last import line end, handling multi-line imports (open parens).
            last_import_end = -1   # last line of last import (incl. closing paren)
            first_import_idx = -1
            in_multiline = False
            for i, line in enumerate(lines):
                stripped_l = line.strip()
                if in_multiline:
                    if stripped_l.startswith(")"):
                        last_import_end = i
                        in_multiline = False
                    continue
                if stripped_l.startswith("from __future__"):
                    continue
                if stripped_l.startswith("import ") or stripped_l.startswith("from "):
                    if first_import_idx == -1:
                        first_import_idx = i
                    last_import_end = i
                    # Multi-line import: `from x import (\n  ...\n)`
                    if "(" in stripped_l and ")" not in stripped_l.split("(", 1)[1]:
                        in_multiline = True
                elif stripped_l and not stripped_l.startswith("#") \
                        and last_import_end != -1:
                    break

            if not has_structlog and first_import_idx != -1:
                lines.insert(first_import_idx, "import structlog")
                last_import_end += 1  # adjust for inserted line

            if not has_log_var and last_import_end != -1:
                insert_after = last_import_end + 1
                lines.insert(insert_after, "log = structlog.get_logger(__name__)")
                lines.insert(insert_after, "")

        for line in lines:
            stripped = line.lstrip()
            indent = line[:len(line) - len(stripped)]
            indent_level = len(indent)

            # Track __main__ blocks — skip print() inside them
            if re.match(r'if\s+__name__\s*==\s*["\']__main__["\']', stripped):
                in_main_block = True
                main_indent = indent_level
                new_lines.append(line)
                continue
            if in_main_block and stripped and indent_level <= main_indent and not stripped.startswith("#"):
                in_main_block = False

            if in_main_block:
                new_lines.append(line)
                continue

            # Replace print() with log.info()
            match = re.match(r'print\((.*)\)\s*(?:#.*)?$', stripped)
            if match:
                arg = match.group(1)
                new_lines.append(f"{indent}log.info({arg})")
                modified = True
                continue

            new_lines.append(line)

        if modified:
            abs_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            verify = _run_cmd([".venv/bin/ruff", "check", fp])
            if verify.returncode != 0 and "error" in verify.stdout.lower():
                _run_cmd(["git", "checkout", "--", fp])
                log.warning("tier1_print_revert", file=fp, reason=verify.stdout[:200])
            else:
                fixed_files.append(fp)

    return fixed_files, None


def _fix_date_format_shell(file_paths: list[str]) -> tuple[list[str], str | None]:
    """Fix $(date) to $(date '+%Y-%m-%d %H:%M:%S') in shell scripts."""
    fixed_files = []
    for fp in file_paths:
        abs_path = PROJECT_DIR / fp
        if not abs_path.exists() or not fp.endswith(".sh"):
            continue

        try:
            content = abs_path.read_text(encoding="utf-8")
        except Exception:
            continue

        # Replace bare $(date) that doesn't already have a format
        new_content = re.sub(
            r"\$\(date\)(?!\s*\+)",
            "$(date '+%Y-%m-%d %H:%M:%S')",
            content,
        )
        if new_content != content:
            abs_path.write_text(new_content, encoding="utf-8")
            fixed_files.append(fp)

    return fixed_files, None


def _fix_dead_code(file_paths: list[str]) -> tuple[list[str], str | None]:
    """Fix dead code via ruff --select F841 (unused variables)."""
    fixed_files = []
    for fp in file_paths:
        abs_path = PROJECT_DIR / fp
        if not abs_path.exists() or not fp.endswith(".py"):
            continue
        try:
            _run_cmd([".venv/bin/ruff", "check", "--select", "F841",
                      "--fix", "--unsafe-fixes", fp])
            diff = _run_cmd(["git", "diff", "--stat", fp])
            if diff.stdout.strip():
                fixed_files.append(fp)
        except Exception as e:
            return fixed_files, str(e)
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
    elif "redundant" in title_lower and "import" in title_lower:
        fixed_files, error = _fix_unused_imports(file_paths)
    elif "print" in title_lower or "structlog" in title_lower:
        fixed_files, error = _fix_print_to_structlog(file_paths)
    elif "date" in title_lower and ("format" in title_lower or "locale" in title_lower
                                     or "$(date)" in title_lower):
        fixed_files, error = _fix_date_format_shell(file_paths)
    elif "dead code" in title_lower or "unreachable" in title_lower:
        fixed_files, error = _fix_dead_code(file_paths)
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
        for fp in fixed_files:
            _run_cmd(["git", "checkout", "--", fp])
        _mark_attempted(finding_ids)
        return {"fixed": False, "files_modified": [], "error": detail}

    _mark_resolved(finding_ids)
    log.info("tier1_success",
             cluster_id=cluster["cluster_id"],
             fixed_files=fixed_files)

    return {"fixed": True, "files_modified": fixed_files, "error": None}
