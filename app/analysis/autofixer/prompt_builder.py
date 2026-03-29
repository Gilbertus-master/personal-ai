"""
Prompt builder — constructs LLM prompts from cluster + context.
"""
from __future__ import annotations

from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _format_resolved_examples(resolved: list[dict]) -> str:
    """Format resolved findings as examples for the prompt."""
    if not resolved:
        return ""

    lines = ["\n## Previously Fixed Similar Issues (use as reference)\n"]
    for r in resolved:
        lines.append(f"- **{r['file_path']}**: {r['title']}")
        if r["suggested_fix"]:
            lines.append(f"  Fix applied: {r['suggested_fix'][:200]}")
    return "\n".join(lines)


def _format_findings_list(findings: list[dict]) -> str:
    """Format list of findings for the prompt."""
    lines = []
    for i, f in enumerate(findings, 1):
        loc = ""
        if f["line_start"]:
            end = f["line_end"] or f["line_start"]
            loc = f" (lines {f['line_start']}-{end})"

        abs_path = str(PROJECT_DIR / f["file_path"])
        lines.append(
            f"\n### Finding {i}: {abs_path}{loc}\n"
            f"**Severity**: {f['severity']}\n"
            f"**Description**: {f['description']}\n"
            f"**Suggested fix**: {f.get('suggested_fix') or 'Use your judgment.'}"
        )
    return "\n".join(lines)


def _format_file_contexts(file_contents: dict[str, str]) -> str:
    """Format file contents for the prompt."""
    lines = ["\n## File Contents\n"]
    for fp, content in file_contents.items():
        abs_path = str(PROJECT_DIR / fp)
        lines.append(f"### {abs_path}\n```\n{content}\n```\n")
    return "\n".join(lines)


def get_budget(cluster_size: int) -> float:
    """Determine budget based on cluster size."""
    if cluster_size <= 1:
        return 0.50
    if cluster_size <= 5:
        return 1.00
    return 2.00


def build_fix_prompt(cluster: dict, context: dict) -> str:
    """Build the full user prompt for a tier-2 LLM fix session.

    For multi-file clusters, instructs the LLM to fix the pattern across all files.
    Includes resolved examples and project conventions for context.
    """
    findings = cluster["findings"]
    is_multi = len(findings) > 1
    attempt_info = ""
    if findings[0].get("fix_attempt_count", 0) > 0:
        attempt_info = (
            "\n**Note**: Previous fix attempt(s) failed. "
            "The bug may be in a DIFFERENT file than file_path. "
            "Trace the actual source carefully.\n"
        )

    if is_multi:
        header = (
            f"The project is at {PROJECT_DIR}.\n\n"
            f"Fix the following **pattern** across **{len(findings)} files** in one session.\n"
            f"All findings share the same issue: **[{cluster['category']}] {cluster['title']}**\n"
            f"{attempt_info}\n"
            f"Fix ALL files below — do NOT skip any."
        )
    else:
        f = findings[0]
        abs_path = str(PROJECT_DIR / f["file_path"])
        header = (
            f"The project is at {PROJECT_DIR}.\n\n"
            f"Fix the following issue in {abs_path}:\n"
            f"**Severity**: {f['severity']}\n"
            f"**Category**: {f['category']}\n"
            f"**Title**: {f['title']}\n"
            f"{attempt_info}"
        )

    findings_section = _format_findings_list(findings)
    context_section = _format_file_contexts(context["file_contents"])
    conventions = f"\n{context['project_conventions']}\n"
    examples = _format_resolved_examples(context["resolved_similar"])

    instructions = (
        "\n## Instructions\n"
        "1. Read each file mentioned above with the Read tool\n"
        "2. IMPORTANT: If the bug is NOT in the listed file, use Grep to find the actual source\n"
        "3. Apply fixes using the Edit tool — minimal changes only\n"
        "4. For Python: run `ruff check <modified_file>` after each fix\n"
        "5. Run: `git diff`\n"
        "6. Output ONLY valid JSON (no markdown fences):\n"
        '```\n{"fixed": true, "changes_summary": "...", '
        '"files_modified": ["path1.py", "path2.py"], "error": null}\n```'
    )

    prompt = "\n".join([
        header,
        findings_section,
        context_section,
        conventions,
        examples,
        instructions,
    ])

    log.info("prompt_built",
             cluster_id=cluster["cluster_id"],
             findings=len(findings),
             prompt_length=len(prompt))

    return prompt
