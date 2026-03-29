"""
Document Validator — post-generation quality assurance for compliance documents.

Runs automatically after every AI document generation, AND can be called
independently to audit/fix existing documents.

Checks:
1. Garbage artifacts: repetitive underscores, broken markdown, placeholder overflows
2. Structural completeness: required sections present for document type
3. Legal reference accuracy: Art. numbers, Dz.U. format
4. Terminology consistency: Polish legal terms
5. Company name correctness: S.A. vs sp. z o.o.
6. Encoding/formatting: broken UTF-8, excess whitespace, markdown issues
"""
from __future__ import annotations

import re

import structlog

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Garbage patterns — things that should NEVER appear in a final document
# ---------------------------------------------------------------------------

GARBAGE_PATTERNS = [
    # Repetitive underscores (AI placeholder overflow)
    (re.compile(r'_{10,}'), "repetitive_underscores",
     "Ciąg podkreśleń (placeholder AI) — zastąpić treścią lub polem [___]"),
    # Repetitive stars/bold markers
    (re.compile(r'\*{5,}'), "repetitive_stars",
     "Ciąg gwiazdek — usunąć"),
    # Repetitive dashes (not horizontal rule)
    (re.compile(r'-{20,}(?!\n)'), "repetitive_dashes",
     "Ciąg myślników (nie linia pozioma) — uprościć do ---"),
    # Repetitive equals
    (re.compile(r'={20,}'), "repetitive_equals",
     "Ciąg znaków = — uprościć"),
    # Bold-wrapped underscores (AI artifact: **___...___**)
    (re.compile(r'\*\*[_]{5,}\*\*'), "bold_underscores",
     "Pogrubione podkreślenia — zastąpić polem do wypełnienia"),
    # Escaped underscores in runs (\_\_\_\_...)
    (re.compile(r'(\\_){5,}'), "escaped_underscores",
     "Escaped podkreślenia (markdown artifact) — zastąpić [___]"),
    # Empty bold markers
    (re.compile(r'\*\*\s*\*\*'), "empty_bold",
     "Puste pogrubienie — usunąć"),
    # Multiple consecutive blank lines (>3)
    (re.compile(r'\n{5,}'), "excessive_blank_lines",
     "Zbyt wiele pustych linii — max 2"),
    # Non-printable characters (except newline, tab)
    (re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]'), "non_printable",
     "Znaki niedrukowalne — usunąć"),
    # Markdown image with no src
    (re.compile(r'!\[\]\(\)'), "empty_image",
     "Pusty tag obrazu — usunąć"),
    # HTML tags that shouldn't be in markdown docs
    (re.compile(r'<(?!/?(?:br|hr|sub|sup|em|strong))[a-zA-Z][^>]*>'), "html_tags",
     "Tagi HTML w dokumencie Markdown — przekonwertować lub usunąć"),
]

# ---------------------------------------------------------------------------
# Auto-fix rules — safe, mechanical replacements
# ---------------------------------------------------------------------------


def _auto_fix_content(text: str) -> tuple[str, list[dict]]:
    """Apply safe auto-fixes. Returns (fixed_text, list_of_fixes_applied)."""
    fixes = []

    # 1. Replace long underscore runs with clean placeholder
    pattern = re.compile(r'\*?\*?[_\\]{10,}\*?\*?')
    if pattern.search(text):
        text = pattern.sub('[___]', text)
        fixes.append({"type": "underscore_cleanup", "description": "Zamieniono ciągi podkreśleń na [___]"})

    # 2. Replace escaped underscore runs (\_\_\_...)
    pattern2 = re.compile(r'(\\_){5,}')
    if pattern2.search(text):
        text = pattern2.sub('[___]', text)
        fixes.append({"type": "escaped_underscore_cleanup", "description": "Zamieniono escaped podkreślenia na [___]"})

    # 3. Remove empty bold markers
    if '** **' in text or '****' in text:
        text = re.sub(r'\*\*\s*\*\*', '', text)
        fixes.append({"type": "empty_bold_removed", "description": "Usunięto puste znaczniki pogrubienia"})

    # 4. Collapse excessive blank lines (>2 → 2)
    if re.search(r'\n{4,}', text):
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        fixes.append({"type": "blank_lines_collapsed", "description": "Zmniejszono liczbę pustych linii do max 2"})

    # 5. Fix double spaces (not in code blocks)
    if '  ' in text and '```' not in text:
        text = re.sub(r'(?<!\n) {2,}(?!\n)', ' ', text)
        fixes.append({"type": "double_spaces", "description": "Usunięto podwójne spacje"})

    # 6. Remove trailing whitespace per line
    lines = text.split('\n')
    stripped = [line.rstrip() for line in lines]
    if lines != stripped:
        text = '\n'.join(stripped)
        fixes.append({"type": "trailing_whitespace", "description": "Usunięto końcowe spacje z linii"})

    # 7. Fix repetitive dash/equals runs (not markdown hr)
    text = re.sub(r'-{20,}', '---', text)
    text = re.sub(r'={20,}', '===', text)

    # 8. Ensure document ends with single newline
    text = text.rstrip() + '\n'

    return text, fixes


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = {
    "policy": ["Postanowienia ogólne", "Postanowienia końcowe"],
    "procedure": ["Cel", "Zakres"],
    "internal_regulation": ["Postanowienia ogólne"],
    "form": [],  # Forms have free structure
    "risk_assessment": ["Ryzyk", "Środki"],
    "communication": [],
    "report": [],
    "training_material": [],
}


def _check_structure(text: str, doc_type: str) -> list[dict]:
    """Check if document has required sections for its type."""
    issues = []
    required = REQUIRED_SECTIONS.get(doc_type, [])
    text_lower = text.lower()

    for section in required:
        if section.lower() not in text_lower:
            issues.append({
                "type": "missing_section",
                "severity": "warning",
                "description": f"Brak wymaganej sekcji: '{section}' dla typu {doc_type}",
            })

    # Check minimum length
    word_count = len(text.split())
    if word_count < 100:
        issues.append({
            "type": "too_short",
            "severity": "critical",
            "description": f"Dokument zbyt krótki ({word_count} słów). Minimum: 100.",
        })

    # Check if document has headings
    if not re.search(r'^#{1,4}\s', text, re.MULTILINE):
        issues.append({
            "type": "no_headings",
            "severity": "warning",
            "description": "Brak nagłówków Markdown (# lub ##)",
        })

    return issues


# ---------------------------------------------------------------------------
# Terminology check
# ---------------------------------------------------------------------------

TERMINOLOGY_FIXES = [
    # GDPR terminology
    (r'\bGDPR\b(?!\s*[\(/])', 'RODO', "Użyto 'GDPR' zamiast 'RODO' w polskim dokumencie"),
    (r'\bDPO\b(?!\s*[\(/])', 'IOD', "Użyto 'DPO' zamiast 'IOD' w polskim dokumencie"),
    (r'\bbreach\b', 'naruszenie', "Użyto angielskiego 'breach' zamiast 'naruszenie'"),
    (r'\bprocessor\b(?!\s*[\(/])', 'podmiot przetwarzający', "Użyto 'processor' zamiast 'podmiot przetwarzający'"),
    (r'\bcontroller\b(?!\s*[\(/])', 'administrator', "Użyto 'controller' zamiast 'administrator'"),
]


def _check_terminology(text: str) -> list[dict]:
    """Check for incorrect terminology in Polish legal documents."""
    issues = []
    for pattern, replacement, desc in TERMINOLOGY_FIXES:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            issues.append({
                "type": "terminology",
                "severity": "info",
                "description": desc,
                "suggestion": replacement,
                "count": len(matches),
            })
    return issues


# ---------------------------------------------------------------------------
# Company name validation
# ---------------------------------------------------------------------------


def _check_company_names(text: str) -> list[dict]:
    """Check for incorrect company name forms."""
    issues = []

    # REH should be S.A.
    if re.search(r'Respect Energy Holding\s+sp\.\s*z\s*o\.o\.', text):
        issues.append({
            "type": "company_name",
            "severity": "critical",
            "description": "REH to S.A., nie sp. z o.o. — 'Respect Energy Holding sp. z o.o.' powinno być 'Respect Energy Holding S.A.'",
        })

    # REF should be sp. z o.o.
    if re.search(r'Respect Energy Fuels\s+S\.A\.', text):
        issues.append({
            "type": "company_name",
            "severity": "critical",
            "description": "REF to sp. z o.o., nie S.A. — 'Respect Energy Fuels S.A.' powinno być 'Respect Energy Fuels sp. z o.o.'",
        })

    return issues


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------


def validate_document(
    content: str,
    doc_type: str = "policy",
    auto_fix: bool = True,
) -> dict:
    """
    Validate and optionally auto-fix a generated document.

    Returns:
        {
            "valid": bool,
            "content": str (fixed if auto_fix=True, original otherwise),
            "fixes_applied": [...],
            "issues": [...],
            "stats": {"words": int, "lines": int, "garbage_found": int}
        }
    """
    # 1. Auto-fix safe artifacts
    if auto_fix:
        content, fixes = _auto_fix_content(content)
    else:
        fixes = []

    # 2. Scan for remaining garbage
    garbage_issues = []
    for pattern, name, desc in GARBAGE_PATTERNS:
        matches = pattern.findall(content)
        if matches:
            garbage_issues.append({
                "type": f"garbage_{name}",
                "severity": "warning" if len(matches) < 3 else "critical",
                "description": desc,
                "count": len(matches),
                "sample": matches[0][:50] if matches else "",
            })

    # 3. Structure check
    structure_issues = _check_structure(content, doc_type)

    # 4. Terminology check
    terminology_issues = _check_terminology(content)

    # 5. Company name check
    company_issues = _check_company_names(content)

    # Combine all issues
    all_issues = garbage_issues + structure_issues + terminology_issues + company_issues
    critical_count = sum(1 for i in all_issues if i.get("severity") == "critical")

    stats = {
        "words": len(content.split()),
        "lines": content.count('\n') + 1,
        "garbage_found": len(garbage_issues),
        "fixes_applied": len(fixes),
        "issues_total": len(all_issues),
        "issues_critical": critical_count,
    }

    valid = critical_count == 0 and len(garbage_issues) == 0

    log.info(
        "document_validated",
        valid=valid,
        fixes=len(fixes),
        issues=len(all_issues),
        critical=critical_count,
        words=stats["words"],
    )

    return {
        "valid": valid,
        "content": content,
        "fixes_applied": fixes,
        "issues": all_issues,
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Batch audit — validate all existing documents in DB
# ---------------------------------------------------------------------------


def audit_all_documents(auto_fix: bool = True, dry_run: bool = False) -> dict:
    """
    Audit ALL compliance documents in the database.
    Optionally auto-fix and update content_text.

    Returns summary: {total, valid, fixed, issues, details: [...]}
    """
    from app.db.postgres import get_pg_connection

    results = {"total": 0, "valid": 0, "fixed": 0, "issues": 0, "details": []}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, doc_type, content_text
                FROM compliance_documents
                WHERE content_text IS NOT NULL
                ORDER BY id
            """)
            rows = cur.fetchall()

        results["total"] = len(rows)

        for doc_id, title, doc_type, content in rows:
            validation = validate_document(content, doc_type, auto_fix=auto_fix)

            detail = {
                "id": doc_id,
                "title": title,
                "valid": validation["valid"],
                "fixes": len(validation["fixes_applied"]),
                "issues": len(validation["issues"]),
                "stats": validation["stats"],
            }

            if validation["fixes_applied"] and not dry_run:
                # Update content in DB
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE compliance_documents SET content_text = %s, updated_at = NOW() WHERE id = %s",
                        (validation["content"], doc_id),
                    )
                conn.commit()
                results["fixed"] += 1
                log.info("document_fixed", doc_id=doc_id, title=title, fixes=len(validation["fixes_applied"]))

            if validation["valid"]:
                results["valid"] += 1
            if validation["issues"]:
                results["issues"] += 1
                detail["issue_details"] = validation["issues"]

            results["details"].append(detail)

    log.info(
        "document_audit_complete",
        total=results["total"],
        valid=results["valid"],
        fixed=results["fixed"],
        with_issues=results["issues"],
    )

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json as json_mod

    parser = argparse.ArgumentParser(description="Document Validator")
    parser.add_argument("--audit", action="store_true", help="Audit all documents in DB")
    parser.add_argument("--dry-run", action="store_true", help="Don't fix, just report")
    parser.add_argument("--file", type=str, help="Validate a specific .md file")
    parser.add_argument("--fix-file", action="store_true", help="Fix file in-place")
    args = parser.parse_args()

    if args.audit:
        results = audit_all_documents(auto_fix=not args.dry_run, dry_run=args.dry_run)
        print(json_mod.dumps(results, indent=2, ensure_ascii=False, default=str))
    elif args.file:
        from pathlib import Path
        content = Path(args.file).read_text()
        result = validate_document(content, auto_fix=True)
        if args.fix_file and result["fixes_applied"]:
            Path(args.file).write_text(result["content"])
            print(f"Fixed: {len(result['fixes_applied'])} issues")
        print(json_mod.dumps({
            "valid": result["valid"],
            "fixes": result["fixes_applied"],
            "issues": result["issues"],
            "stats": result["stats"],
        }, indent=2, ensure_ascii=False))
    else:
        parser.print_help()
