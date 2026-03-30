"""
Document Generator — AI-powered generacja dokumentów compliance.

Typy dokumentów:
- policy: polityka wewnętrzna (np. Polityka Ochrony Danych Osobowych)
- procedure: procedura (np. Procedura reagowania na incydent RODO)
- form: formularz (np. Rejestr czynności przetwarzania)
- internal_regulation: regulamin wewnętrzny (np. Regulamin pracy zdalnej)
- training_material: materiały szkoleniowe
- report: raport compliance
- risk_assessment: ocena ryzyka (pisemna)
- communication: komunikat do pracowników/interesariuszy

Każdy dokument generowany w języku polskim, z numeracją paragrafów,
nagłówkami sekcji, datą, podpisami, klauzulami.
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from datetime import date, datetime, timezone
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

DOC_TYPE_PL = {
    "policy": "politykę wewnętrzną",
    "procedure": "procedurę",
    "form": "formularz",
    "internal_regulation": "regulamin wewnętrzny",
    "training_material": "materiały szkoleniowe",
    "report": "raport compliance",
    "risk_assessment": "ocenę ryzyka",
    "communication": "komunikat",
}

SIGNATURE_REQUIRED = {"policy", "internal_regulation", "procedure"}


def _build_system_prompt(
    doc_type: str,
    matter: dict,
    area: dict | None,
    title: str,
    signers: list[dict],
    today: str,
) -> str:
    """Build system prompt based on document type."""
    doc_type_pl = DOC_TYPE_PL.get(doc_type, doc_type)
    legal_analysis = matter.get("legal_analysis") or "Brak analizy prawnej."
    obligations = matter.get("obligations_report") or "Brak raportu obowiązków."
    regs = ""
    if area and area.get("key_regulations"):
        regs = "\n".join(f"- {r}" for r in area["key_regulations"])

    signers_str = ", ".join(
        f'{s["name"]} ({s["role"]})' for s in signers
    ) if signers else "Prezes Zarządu"

    base = f"""Jesteś prawnikiem korporacyjnym specjalizującym się w prawie polskim.
Wygeneruj {doc_type_pl} dla polskiej spółki energetycznej.

KONTEKST PRAWNY:
{legal_analysis}

OBOWIĄZKI:
{obligations}

REGULACJE OBSZARU:
{regs or 'Brak szczegółowych regulacji.'}

WYMAGANIA:
- Język polski, formalny styl prawniczy
- Data wejścia w życie: {today}
- Miejsce na podpisy: {signers_str}
- Odwołania do konkretnych aktów prawnych (Dz.U.)
- Klauzula o przeglądzie dokumentu (co 12 miesięcy)

Tytuł: {title}
Spółka: Respect Energy Holding sp. z o.o. / Respect Energy Fuels sp. z o.o."""

    if doc_type in ("policy", "internal_regulation"):
        base += """

STRUKTURA DOKUMENTU:
- Numeracja paragrafów (§1, §2, ...)
- Sekcje: Postanowienia ogólne, Definicje, [treść merytoryczna],
  Obowiązki, Odpowiedzialność, Postanowienia końcowe"""

    elif doc_type == "procedure":
        base += """

STRUKTURA DOKUMENTU:
- Numeracja paragrafów (§1, §2, ...)
- Sekcje: Cel procedury, Zakres stosowania, Definicje,
  Schemat postępowania (krok po kroku), Osoby odpowiedzialne,
  Terminy, Dokumentacja, Szkolenia, Postanowienia końcowe"""

    elif doc_type == "form":
        base += """

STRUKTURA DOKUMENTU:
- Format tabelaryczny z polami do wypełnienia
- Nagłówek z nazwą spółki, datą, numerem dokumentu
- Instrukcja wypełniania"""

    elif doc_type == "training_material":
        base += """

STRUKTURA DOKUMENTU:
- Struktura modułowa: cel szkolenia, agenda, treść (z przykładami),
  pytania kontrolne, test wiedzy (5-10 pytań), certyfikat ukończenia"""

    elif doc_type == "communication":
        base += """

STRUKTURA DOKUMENTU:
- Format komunikatu: Od, Do, Data, Temat, Treść, Załączniki, Podpis"""

    return base


def generate_document(
    matter_id: int,
    doc_type: str,
    title: str | None = None,
    template_hint: str | None = None,
    signers: list[dict] | None = None,
    valid_months: int = 12,
) -> dict[str, Any]:
    """Generuje dokument compliance z użyciem AI.

    Returns: {document_id, title, doc_type, version, requires_signature, signers, status}
    """
    if doc_type not in DOC_TYPE_PL:
        return {"error": "invalid_doc_type", "valid_types": list(DOC_TYPE_PL.keys())}

    # 1. Fetch matter
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.id, m.title, m.legal_analysis, m.obligations_report,
                       m.area_id, a.code as area_code, a.key_regulations
                FROM compliance_matters m
                LEFT JOIN compliance_areas a ON a.id = m.area_id
                WHERE m.id = %s
            """, (matter_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "matter_not_found", "matter_id": matter_id}

    matter = {
        "id": row[0], "title": row[1], "legal_analysis": row[2],
        "obligations_report": row[3], "area_id": row[4],
    }
    area = {"code": row[5], "key_regulations": row[6] or []}

    # 2. Title
    if not title:
        title = f"{DOC_TYPE_PL[doc_type].capitalize()} — {matter['title']}"

    # 3. Signers
    if signers is None:
        signers = [{"name": "Sebastian Jabłoński", "role": "Prezes Zarządu"}]
    signer_records = [
        {"name": s["name"], "role": s["role"], "signed_at": None, "status": "pending"}
        for s in signers
    ]

    today = date.today()
    requires_sig = doc_type in SIGNATURE_REQUIRED

    # 4. Build prompt and call Claude
    system_prompt = _build_system_prompt(
        doc_type, matter, area, title, signers, today.isoformat(),
    )
    user_msg = f"Wygeneruj dokument: {title}"
    if template_hint:
        user_msg += f"\n\nDodatkowe wskazówki: {template_hint}"

    log.info("document_generate_start", matter_id=matter_id, doc_type=doc_type, title=title)

    # Split system: static role prefix (cacheable) + dynamic context
    _STATIC_ROLE = (
        "Jesteś prawnikiem korporacyjnym specjalizującym się w prawie polskim. "
        "Generujesz dokumenty compliance dla polskiej spółki energetycznej."
    )

    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4000,
        temperature=0.2,
        system=[
            {"type": "text", "text": _STATIC_ROLE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": system_prompt},
        ],
        messages=[{"role": "user", "content": user_msg}],
    )
    content_text = resp.content[0].text
    log_anthropic_cost(ANTHROPIC_MODEL, "legal_document_generator", resp.usage)
    log.info("cache_stats",
             cache_creation=getattr(resp.usage, "cache_creation_input_tokens", 0),
             cache_read=getattr(resp.usage, "cache_read_input_tokens", 0))

    # 5. Determine version
    from dateutil.relativedelta import relativedelta
    valid_from = today
    valid_until = today + relativedelta(months=valid_months)
    review_due = valid_until - relativedelta(days=30)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Check existing version for same title + area
            cur.execute("""
                SELECT COALESCE(MAX(version), 0)
                FROM compliance_documents
                WHERE title = %s AND area_id = %s
            """, (title, matter["area_id"]))
            max_ver = cur.fetchall()[0][0]
            version = max_ver + 1

            # 6. Insert
            cur.execute("""
                INSERT INTO compliance_documents
                    (title, doc_type, area_id, matter_id, version, content_text,
                     generated_by, valid_from, valid_until, review_due,
                     requires_signature, signature_status, signers, status)
                VALUES (%s, %s, %s, %s, %s, %s,
                        'ai', %s, %s, %s,
                        %s, %s, %s::jsonb, 'draft')
                RETURNING id
            """, (
                title, doc_type, matter["area_id"], matter_id, version,
                content_text, valid_from, valid_until, review_due,
                requires_sig,
                "pending" if requires_sig else "not_required",
                json.dumps(signer_records),
            ))
            doc_id = cur.fetchall()[0][0]
        conn.commit()

    log.info("document_generated", document_id=doc_id, title=title, version=version)

    return {
        "document_id": doc_id,
        "title": title,
        "doc_type": doc_type,
        "version": version,
        "requires_signature": requires_sig,
        "signers": signer_records,
        "status": "draft",
    }


def list_documents(
    area_code: str | None = None,
    doc_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lista dokumentów compliance z filtrami."""
    conditions = []
    params: list[Any] = []

    if area_code:
        conditions.append("a.code = %s")
        params.append(area_code)
    if doc_type:
        conditions.append("d.doc_type = %s")
        params.append(doc_type)
    if status:
        conditions.append("d.status = %s")
        params.append(status)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT d.id, d.title, d.doc_type, a.code as area_code,
                       d.version, d.status, d.signature_status,
                       d.valid_from, d.valid_until, d.review_due,
                       d.requires_signature, d.created_at
                FROM compliance_documents d
                LEFT JOIN compliance_areas a ON a.id = d.area_id
                {where}
                ORDER BY d.created_at DESC
                LIMIT %s
            """, params)
            rows = cur.fetchall()

    return [
        {
            "id": r[0], "title": r[1], "doc_type": r[2], "area_code": r[3],
            "version": r[4], "status": r[5], "signature_status": r[6],
            "valid_from": r[7].isoformat() if r[7] else None,
            "valid_until": r[8].isoformat() if r[8] else None,
            "review_due": r[9].isoformat() if r[9] else None,
            "requires_signature": r[10],
            "created_at": r[11].isoformat() if r[11] else None,
        }
        for r in rows
    ]


def get_stale_documents(days_overdue: int = 0) -> list[dict[str, Any]]:
    """Dokumenty z review_due <= TODAY + days_overdue i status = 'active'."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.doc_type, a.code as area_code,
                       d.review_due, (CURRENT_DATE - d.review_due) as days_overdue
                FROM compliance_documents d
                LEFT JOIN compliance_areas a ON a.id = d.area_id
                WHERE d.status = 'active'
                  AND d.review_due <= CURRENT_DATE + %s * INTERVAL '1 day'
                ORDER BY d.review_due ASC
            """, (days_overdue,))
            rows = cur.fetchall()

    return [
        {
            "id": r[0], "title": r[1], "doc_type": r[2], "area_code": r[3],
            "review_due": r[4].isoformat() if r[4] else None,
            "days_overdue": r[5],
        }
        for r in rows
    ]


def approve_document(document_id: int, approved_by: str = "sebastian") -> dict[str, Any]:
    """Zatwierdza dokument. Poprzednią wersję oznacza jako 'superseded'."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, area_id, status
                FROM compliance_documents WHERE id = %s
            """, (document_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "document_not_found", "document_id": document_id}

            doc_title, area_id, current_status = row[1], row[2], row[3]
            if current_status not in ("draft", "review"):
                return {"error": "invalid_status", "current_status": current_status,
                        "hint": "Only draft/review documents can be approved"}

            # Supersede previous versions
            cur.execute("""
                UPDATE compliance_documents
                SET status = 'superseded', updated_at = NOW()
                WHERE title = %s AND area_id = %s AND id != %s
                  AND status IN ('approved', 'active')
            """, (doc_title, area_id, document_id))
            superseded = cur.rowcount

            # Approve current
            cur.execute("""
                UPDATE compliance_documents
                SET status = 'approved', approved_by = %s, approved_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (approved_by, document_id))
        conn.commit()

    log.info("document_approved", document_id=document_id, approved_by=approved_by,
             superseded_count=superseded)

    return {
        "document_id": document_id,
        "status": "approved",
        "approved_by": approved_by,
        "superseded_count": superseded,
    }


def sign_document(document_id: int, signer_name: str) -> dict[str, Any]:
    """Rejestruje podpis elektroniczny."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, signers, signature_status, status, requires_signature
                FROM compliance_documents WHERE id = %s
            """, (document_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "document_not_found", "document_id": document_id}

            signers = row[1] or []
            if not row[4]:
                return {"error": "signature_not_required", "document_id": document_id}

            # Find signer
            found = False
            all_signed = True
            for s in signers:
                if s["name"] == signer_name:
                    if s["status"] == "signed":
                        return {"error": "already_signed", "signer_name": signer_name}
                    s["signed_at"] = datetime.now(timezone.utc).isoformat()
                    s["status"] = "signed"
                    found = True
                if s["status"] != "signed":
                    all_signed = False

            if not found:
                return {"error": "signer_not_found", "signer_name": signer_name,
                        "available_signers": [s["name"] for s in signers]}

            # Re-check all_signed after update
            all_signed = all(s["status"] == "signed" for s in signers)
            sig_status = "signed" if all_signed else "partially_signed"
            doc_status = "active" if all_signed else row[3]

            cur.execute("""
                UPDATE compliance_documents
                SET signers = %s::jsonb, signature_status = %s,
                    status = %s, updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(signers), sig_status, doc_status, document_id))
        conn.commit()

    log.info("document_signed", document_id=document_id, signer=signer_name,
             signature_status=sig_status)

    return {
        "document_id": document_id,
        "signer_name": signer_name,
        "signature_status": sig_status,
        "all_signed": all_signed,
    }


def run_document_freshness_check() -> dict[str, Any]:
    """Cron: sprawdź freshness dokumentów — zwróć dokumenty wymagające przeglądu."""
    stale = get_stale_documents(days_overdue=0)
    log.info("document_freshness_check", stale_count=len(stale))
    return {"stale_count": len(stale), "documents": stale}


# ---------------------------------------------------------------------------
# Multipass document generation
# ---------------------------------------------------------------------------

def _generate_single_shot(
    ai_client: Anthropic,
    model: str,
    matter_id: int,
    doc_type: str,
    title: str,
    company_context: str | None = None,
) -> dict[str, Any]:
    """Single-shot generation with max_tokens=16000 and truncation detection."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.id, m.title, m.legal_analysis, m.obligations_report,
                       m.area_id, a.code as area_code, a.key_regulations
                FROM compliance_matters m
                LEFT JOIN compliance_areas a ON a.id = m.area_id
                WHERE m.id = %s
            """, (matter_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "matter_not_found", "matter_id": matter_id}

    matter = {
        "id": row[0], "title": row[1], "legal_analysis": row[2],
        "obligations_report": row[3], "area_id": row[4],
    }
    area = {"code": row[5], "key_regulations": row[6] or []}

    signers = [{"name": "Sebastian Jabłoński", "role": "Prezes Zarządu"}]
    today = date.today().isoformat()

    system_prompt = _build_system_prompt(doc_type, matter, area, title, signers, today)
    if company_context:
        system_prompt += f"\n\nKONTEKST FIRMOWY:\n{company_context}"

    user_msg = f"Wygeneruj kompletny dokument: {title}"

    _STATIC_ROLE = (
        "Jesteś prawnikiem korporacyjnym specjalizującym się w prawie polskim. "
        "Generujesz dokumenty compliance dla polskiej spółki energetycznej."
    )

    resp = ai_client.messages.create(
        model=model,
        max_tokens=16000,
        temperature=0.2,
        system=[
            {"type": "text", "text": _STATIC_ROLE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": system_prompt},
        ],
        messages=[{"role": "user", "content": user_msg}],
    )
    content_text = resp.content[0].text
    log_anthropic_cost(model, "legal_document_single_shot", resp.usage)

    is_complete = resp.stop_reason != "max_tokens"
    if resp.stop_reason == "max_tokens":
        log.warning("single_shot_truncated", matter_id=matter_id, title=title,
                     stop_reason=resp.stop_reason)

    word_count = len(content_text.split())
    sections = [line for line in content_text.split("\n") if line.strip().startswith("§") or line.strip().startswith("#")]

    return {
        "content": content_text,
        "is_complete": is_complete,
        "word_count": word_count,
        "section_count": len(sections),
        "stop_reason": resp.stop_reason,
    }


def generate_document_multipass(
    matter_id: int,
    doc_type: str,
    title: str,
    company_context: str | None = None,
) -> dict[str, Any]:
    """3-pass document generation: outline -> per-section -> quality check.

    Pass 1: Generate outline (2000 tokens)
    Pass 2: Generate each section (4000 tokens each, continuation if truncated)
    Pass 3: Quality check and score

    Returns: {content, is_complete, word_count, section_count, quality_score, generation_method}
    """
    if doc_type not in DOC_TYPE_PL:
        return {"error": "invalid_doc_type", "valid_types": list(DOC_TYPE_PL.keys())}

    # Fetch matter context
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.id, m.title, m.legal_analysis, m.obligations_report,
                       m.area_id, a.code as area_code, a.key_regulations
                FROM compliance_matters m
                LEFT JOIN compliance_areas a ON a.id = m.area_id
                WHERE m.id = %s
            """, (matter_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "matter_not_found", "matter_id": matter_id}

    matter = {
        "id": row[0], "title": row[1], "legal_analysis": row[2],
        "obligations_report": row[3], "area_id": row[4],
    }
    area = {"code": row[5], "key_regulations": row[6] or []}

    doc_type_pl = DOC_TYPE_PL.get(doc_type, doc_type)
    legal_analysis = matter.get("legal_analysis") or "Brak analizy prawnej."

    log.info("multipass_start", matter_id=matter_id, doc_type=doc_type, title=title)

    _STATIC_ROLE = (
        "Jesteś prawnikiem korporacyjnym specjalizującym się w prawie polskim. "
        "Generujesz dokumenty compliance dla polskiej spółki energetycznej."
    )

    context_block = ""
    if company_context:
        context_block = f"\nKONTEKST FIRMOWY:\n{company_context}\n"

    # ── PASS 1: Outline ──────────────────────────────────────────────────
    outline_prompt = (
        f"Wygeneruj szczegółowy OUTLINE (spis treści z opisami sekcji) "
        f"dla dokumentu typu {doc_type_pl}.\n"
        f"Tytuł: {title}\n"
        f"Analiza prawna:\n{legal_analysis[:3000]}\n{context_block}\n"
        f"Format: lista sekcji z krótkim opisem zawartości każdej sekcji. "
        f"Każda sekcja w formacie: '## SEKCJA N: Tytuł sekcji\\nOpis zawartości'"
    )

    try:
        resp_outline = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            temperature=0.2,
            system=[
                {"type": "text", "text": _STATIC_ROLE, "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": outline_prompt}],
        )
        log_anthropic_cost(ANTHROPIC_MODEL, "legal_multipass_outline", resp_outline.usage)
        outline_text = resp_outline.content[0].text.strip()
        if resp_outline.stop_reason == "max_tokens":
            log.warning("multipass_outline_truncated", matter_id=matter_id)
    except Exception as e:
        log.error("multipass_outline_error", error=str(e), matter_id=matter_id)
        # Fallback to single-shot
        result = _generate_single_shot(client, ANTHROPIC_MODEL, matter_id, doc_type, title, company_context)
        result["generation_method"] = "single_shot_fallback"
        result["quality_score"] = 0.0
        return result

    # Parse sections from outline
    sections = []
    for line in outline_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## SEKCJA") or stripped.startswith("## ") or stripped.startswith("# "):
            sections.append(stripped.lstrip("#").strip())

    if not sections:
        # Fallback: split by numbered items
        for line in outline_text.split("\n"):
            stripped = line.strip()
            if stripped and (stripped[0].isdigit() or stripped.startswith("§")):
                sections.append(stripped)

    if not sections:
        log.warning("multipass_no_sections_found", matter_id=matter_id)
        result = _generate_single_shot(client, ANTHROPIC_MODEL, matter_id, doc_type, title, company_context)
        result["generation_method"] = "single_shot_fallback"
        result["quality_score"] = 0.0
        return result

    log.info("multipass_outline_done", sections=len(sections))

    # ── PASS 2: Per-section generation ────────────────────────────────────
    full_content_parts = []
    signers = [{"name": "Sebastian Jabłoński", "role": "Prezes Zarządu"}]
    today = date.today().isoformat()

    system_prompt = _build_system_prompt(doc_type, matter, area, title, signers, today)
    if company_context:
        system_prompt += f"\n\nKONTEKST FIRMOWY:\n{company_context}"

    for i, section_title in enumerate(sections):
        section_prompt = (
            f"Wygeneruj TYLKO sekcję {i+1}/{len(sections)} dokumentu '{title}'.\n"
            f"Sekcja: {section_title}\n\n"
            f"OUTLINE DOKUMENTU:\n{outline_text}\n\n"
            f"Pisz TYLKO tę sekcję. Zachowaj numerację paragrafów spójną z dokumentem."
        )

        try:
            resp_section = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4000,
                temperature=0.2,
                system=[
                    {"type": "text", "text": _STATIC_ROLE, "cache_control": {"type": "ephemeral"}},
                    {"type": "text", "text": system_prompt},
                ],
                messages=[{"role": "user", "content": section_prompt}],
            )
            log_anthropic_cost(ANTHROPIC_MODEL, "legal_multipass_section", resp_section.usage)
            section_text = resp_section.content[0].text.strip()

            # Continuation if truncated
            if resp_section.stop_reason == "max_tokens":
                log.warning("multipass_section_truncated", section=i+1, title=section_title)
                cont_prompt = (
                    f"Kontynuuj generowanie sekcji '{section_title}'. "
                    f"Dotychczasowa treść:\n{section_text[-1000:]}\n\n"
                    f"Kontynuuj od miejsca przerwania."
                )
                resp_cont = client.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=4000,
                    temperature=0.2,
                    system=[
                        {"type": "text", "text": _STATIC_ROLE, "cache_control": {"type": "ephemeral"}},
                        {"type": "text", "text": system_prompt},
                    ],
                    messages=[{"role": "user", "content": cont_prompt}],
                )
                log_anthropic_cost(ANTHROPIC_MODEL, "legal_multipass_continuation", resp_cont.usage)
                section_text += "\n" + resp_cont.content[0].text.strip()
                if resp_cont.stop_reason == "max_tokens":
                    log.warning("multipass_continuation_also_truncated", section=i+1)

            full_content_parts.append(section_text)
        except Exception as e:
            log.error("multipass_section_error", section=i+1, error=str(e))
            full_content_parts.append(f"[SEKCJA {i+1}: {section_title} — BŁĄD GENEROWANIA]")

    full_content = "\n\n".join(full_content_parts)

    # ── PASS 3: Quality check ────────────────────────────────────────────
    quality_score = 0.0
    try:
        qc_prompt = (
            f"Oceń jakość poniższego dokumentu prawnego typu {doc_type_pl}.\n"
            f"Tytuł: {title}\n\n"
            f"DOKUMENT:\n{full_content[:8000]}\n\n"
            f"Oceń w skali 0.0-1.0 pod kątem:\n"
            f"1. Kompletność (czy wszystkie sekcje są)\n"
            f"2. Poprawność prawna (odwołania do ustaw)\n"
            f"3. Spójność (numeracja, format)\n"
            f"4. Praktyczność (czy nadaje się do użytku)\n\n"
            f"Odpowiedz TYLKO jedną liczbą (np. 0.85)."
        )

        resp_qc = client.messages.create(
            model=os.getenv("ANTHROPIC_FAST_MODEL", ANTHROPIC_MODEL),
            max_tokens=100,
            temperature=0.0,
            messages=[{"role": "user", "content": qc_prompt}],
        )
        log_anthropic_cost(
            os.getenv("ANTHROPIC_FAST_MODEL", ANTHROPIC_MODEL),
            "legal_multipass_qc", resp_qc.usage,
        )
        qc_text = resp_qc.content[0].text.strip()
        # Extract float from response
        for token in qc_text.replace(",", ".").split():
            try:
                quality_score = float(token)
                if 0.0 <= quality_score <= 1.0:
                    break
            except ValueError:
                continue
    except Exception as e:
        log.error("multipass_qc_error", error=str(e))
        quality_score = 0.0

    word_count = len(full_content.split())
    section_count = len(sections)
    is_complete = all(
        "BŁĄD GENEROWANIA" not in part for part in full_content_parts
    )

    log.info("multipass_done",
             matter_id=matter_id, word_count=word_count,
             section_count=section_count, quality_score=quality_score,
             is_complete=is_complete)

    return {
        "content": full_content,
        "is_complete": is_complete,
        "word_count": word_count,
        "section_count": section_count,
        "quality_score": quality_score,
        "generation_method": "multipass",
    }
