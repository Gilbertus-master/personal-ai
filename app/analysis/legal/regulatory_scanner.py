"""
Regulatory Scanner — skanuje ingested data w poszukiwaniu zmian regulacyjnych.

Szuka w chunkach keywords: rozporządzenie, nowelizacja, Dz.U., obwieszczenie,
koncesja, URE, UODO, AML, KNF, CSRD, ESRS, zmiana przepisów, regulacja, ustawa,
dyrektywa, compliance, obowiązek, termin, kara, sankcja.

Gdy znajdzie nową regulację → auto-tworzy compliance_matter typu 'new_regulation' lub 'regulation_change'.
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

REGULATORY_KEYWORDS = [
    "rozporządzenie", "nowelizacja", "Dz.U.", "dziennik ustaw",
    "obwieszczenie", "koncesja", "URE", "UODO", "GIIF", "KNF",
    "CSRD", "ESRS", "zmiana przepisów", "nowa regulacja", "ustawa",
    "dyrektywa", "compliance", "obowiązek regulacyjny", "kara pieniężna",
    "sankcja", "termin sprawozdawczy", "raportowanie ESG", "AML",
    "przeciwdziałanie praniu", "ochrona danych", "RODO", "GDPR",
]

# Area code mapping for auto-classification
AREA_CODE_MAP = {
    "URE": "URE", "koncesja": "URE", "prawo energetyczne": "URE",
    "RODO": "RODO", "GDPR": "RODO", "ochrona danych": "RODO", "UODO": "RODO",
    "AML": "AML", "GIIF": "AML", "przeciwdziałanie praniu": "AML",
    "KNF": "ESG", "CSRD": "ESG", "ESRS": "ESG", "raportowanie ESG": "ESG",
}


def _chunk_mentions_regulation(text: str) -> bool:
    """Szybki pre-filter: czy tekst zawiera którykolwiek z REGULATORY_KEYWORDS (case-insensitive)."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in REGULATORY_KEYWORDS)


def _build_keyword_ilike_conditions() -> tuple[str, list[str]]:
    """Build SQL ILIKE conditions for keyword matching."""
    conditions = []
    params = []
    for kw in REGULATORY_KEYWORDS:
        conditions.append("c.text ILIKE %s")
        params.append(f"%{kw}%")
    return " OR ".join(conditions), params


def _classify_with_ai(text: str, source_info: str) -> dict[str, Any] | None:
    """Wywołaj Claude Haiku do klasyfikacji tekstu regulacyjnego."""
    _SYSTEM_CLASSIFY = (
        "Analizujesz teksty pod kątem nowych lub zmienionych regulacji prawnych "
        "dotyczących spółki energetycznej w Polsce.\n\n"
        "Jeśli tekst zawiera regulację, zwróć WYŁĄCZNIE JSON (bez markdown):\n"
        '{"is_regulatory": true, "title": "krótki tytuł regulacji", '
        '"area_code": "URE|RODO|AML|KSH|ESG|LABOR|TAX|CONTRACT|INTERNAL_AUDIT", '
        '"matter_type": "new_regulation|regulation_change", '
        '"description": "opis w 2-3 zdaniach", '
        '"source_reference": "Dz.U. ... lub inny identyfikator", '
        '"priority": "low|medium|high|critical"}\n\n'
        'Jeśli tekst NIE zawiera informacji o regulacji — zwróć WYŁĄCZNIE:\n'
        '{"is_regulatory": false}'
    )

    prompt = f"ŹRÓDŁO: {source_info}\n\nTEKST:\n{text[:3000]}"

    try:
        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=500,
            system=[
                {"type": "text", "text": _SYSTEM_CLASSIFY, "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        log_anthropic_cost(ANTHROPIC_FAST, "regulatory_scanner", response.usage)
        log.info("cache_stats",
                 cache_creation=getattr(response.usage, "cache_creation_input_tokens", 0),
                 cache_read=getattr(response.usage, "cache_read_input_tokens", 0))

        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)
        return result if result.get("is_regulatory") else None

    except (json.JSONDecodeError, IndexError, KeyError) as e:
        log.warning("regulatory_scanner_parse_error", error=str(e))
        return None
    except Exception as e:
        log.error("regulatory_scanner_ai_error", error=str(e))
        return None


def _dedup_matter_exists(title: str) -> bool:
    """Sprawdź czy matter z podobnym tytułem już istnieje (dedup)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Check for exact or very similar title in last 90 days
            cur.execute("""
                SELECT COUNT(*) FROM compliance_matters
                WHERE (title ILIKE %s OR title ILIKE %s)
                  AND created_at > NOW() - INTERVAL '90 days'
            """, (title, f"%{title[:50]}%"))
            return cur.fetchall()[0][0] > 0


def scan_for_regulatory_changes(hours: int = 24) -> dict[str, Any]:
    """Skanuje chunki z ostatnich N godzin pod kątem keywords regulacyjnych.

    1. SELECT chunks WHERE created_at > NOW() - hours AND text ILIKE ANY keyword
    2. Grupuj po document_id
    3. Dla każdej grupy: wywołaj Claude Haiku z promptem klasyfikacyjnym
    4. Dla każdego znalezionego → sprawdź czy nie istnieje już matter z podobnym tytułem (dedup)
    5. Jeśli nowy → create_matter() z odpowiednimi parametrami

    Zwraca: {scanned_chunks: N, regulatory_found: N, matters_created: N, details: [...]}
    """
    from app.analysis.legal_compliance import create_matter, _ensure_tables, _seed_compliance_areas
    _ensure_tables()
    _seed_compliance_areas()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Build keyword conditions
    keyword_sql, keyword_params = _build_keyword_ilike_conditions()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT c.id, c.text, s.source_type, s.source_name,
                       c.document_id, d.created_at
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE d.created_at > %s
                  AND ({keyword_sql})
                ORDER BY c.document_id, d.created_at
            """, [cutoff] + keyword_params)
            chunks = cur.fetchall()

    log.info("regulatory_scan_started", hours=hours, candidate_chunks=len(chunks))

    if not chunks:
        return {
            "scanned_chunks": 0,
            "regulatory_found": 0,
            "matters_created": 0,
            "details": [],
        }

    # Group by document_id
    doc_groups: dict[int | None, list[tuple]] = {}
    for chunk in chunks:
        doc_id = chunk[4]
        doc_groups.setdefault(doc_id, []).append(chunk)

    regulatory_found = 0
    matters_created = 0
    details = []

    for doc_id, doc_chunks in doc_groups.items():
        # Combine text from chunks in same document (max 4000 chars)
        combined_text = ""
        for ch in doc_chunks[:10]:  # Max 10 chunks per document
            combined_text += ch[1][:500] + "\n\n"
            if len(combined_text) > 4000:
                break

        source_info = f"{doc_chunks[0][2]}:{doc_chunks[0][3]}" if doc_chunks[0][3] else str(doc_chunks[0][2])

        # AI classification
        result = _classify_with_ai(combined_text, source_info)
        if not result:
            continue

        regulatory_found += 1
        title = result.get("title", "Nowa regulacja")
        area_code = result.get("area_code", "INTERNAL_AUDIT")
        matter_type = result.get("matter_type", "new_regulation")
        description = result.get("description", "")
        source_ref = result.get("source_reference", "")
        priority = result.get("priority", "medium")

        # Dedup check
        if _dedup_matter_exists(title):
            log.info("regulatory_scan_dedup_skip", title=title)
            details.append({
                "title": title, "area_code": area_code, "action": "skipped_duplicate",
            })
            continue

        # Create matter
        chunk_ids = [ch[0] for ch in doc_chunks[:10]]
        matter = create_matter(
            title=title,
            matter_type=matter_type,
            area_code=area_code,
            description=f"{description}\n\nŹródło: {source_ref}\nZnalezione w: {source_info}",
            priority=priority,
            source_regulation=source_ref,
        )

        # Link source chunk ids
        if matter.get("id"):
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE compliance_matters SET source_chunk_ids = %s WHERE id = %s",
                        (chunk_ids, matter["id"]),
                    )
                conn.commit()

        matters_created += 1
        details.append({
            "title": title,
            "area_code": area_code,
            "matter_type": matter_type,
            "priority": priority,
            "matter_id": matter.get("id"),
            "source_reference": source_ref,
            "action": "created",
        })

        log.info("regulatory_matter_created",
                 matter_id=matter.get("id"), title=title, area=area_code)

    log.info("regulatory_scan_completed",
             scanned_chunks=len(chunks), regulatory_found=regulatory_found,
             matters_created=matters_created)

    return {
        "scanned_chunks": len(chunks),
        "regulatory_found": regulatory_found,
        "matters_created": matters_created,
        "details": details,
    }
