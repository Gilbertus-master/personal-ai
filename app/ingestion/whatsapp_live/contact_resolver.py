"""
Contact resolver for WhatsApp Live pipeline.

Resolves WhatsApp participants to contacts in the DB, using:
1. Phone number match (deterministic, confidence=1.0)
2. JID match (deterministic, confidence=1.0)
3. Push name fuzzy match (probabilistic, confidence=0.7-0.9)
4. Auto-create if no match found

Also provides bootstrap from historical WA export source_names.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

import structlog

from app.db.postgres import get_pg_connection

logger = structlog.get_logger("whatsapp_live.contact_resolver")


# ── Phone normalization ────────────────────────────────────────────────


def normalize_phone(raw: str) -> str | None:
    """Normalize phone number to +XXXXXXXXXXX format.

    '48505441635' → '+48505441635'
    '505441635' → '+48505441635'
    '+48 505-441-635' → '+48505441635'
    Returns None if input is not a valid phone number.
    """
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    if not digits or len(digits) < 7:
        return None
    # Polish numbers: 9 digits → add 48 prefix
    if len(digits) == 9 and digits[0] in "4567":
        digits = "48" + digits
    return f"+{digits}"


def jid_to_phone(jid: str) -> str | None:
    """Extract phone from WA JID if it's phone-based.

    '48505441635@s.whatsapp.net' → '+48505441635'
    '214198726455434@lid' → None (LID format, no phone)
    '120363186705199373@g.us' → None (group)
    """
    if not jid:
        return None
    if jid.endswith("@s.whatsapp.net"):
        num = jid.split("@")[0]
        return normalize_phone(num)
    return None


# ── Contact resolution ─────────────────────────────────────────────────


def resolve_contact(
    jid: str | None = None,
    phone: str | None = None,
    push_name: str | None = None,
) -> int | None:
    """Resolve a WA participant to a contact_id.

    Matching priority:
    1. Phone match (confidence=1.0)
    2. JID match (confidence=1.0)
    3. Push name fuzzy match (confidence=0.7-0.9, threshold=0.8)
    4. Auto-create new contact

    Returns contact_id.
    """
    normalized_phone = normalize_phone(phone) if phone else jid_to_phone(jid)

    # 1. Match by phone
    if normalized_phone:
        contact_id = _find_by_phone(normalized_phone)
        if contact_id:
            _log_match(contact_id, "whatsapp_live", "phone", normalized_phone, 1.0)
            return contact_id

    # 2. Match by JID
    if jid:
        contact_id = _find_by_jid(jid)
        if contact_id:
            _log_match(contact_id, "whatsapp_live", "jid", jid, 1.0)
            return contact_id

    # 3. Fuzzy match by push name
    if push_name and len(push_name) >= 3:
        contact_id, confidence = _find_by_name_fuzzy(push_name)
        if contact_id and confidence >= 0.8:
            _log_match(contact_id, "whatsapp_live", "name_fuzzy", push_name, confidence)
            # Update JID on the contact if we have one
            if jid:
                _update_contact_jid(contact_id, jid, push_name)
            return contact_id

    # 4. Auto-create
    canonical = push_name or (f"+{normalized_phone}" if normalized_phone else None) or jid or "Unknown"
    contact_id = _create_contact(
        canonical_name=canonical,
        jid=jid,
        phone=normalized_phone,
        push_name=push_name,
    )
    _log_match(contact_id, "whatsapp_live", "auto_created", canonical, 0.5)
    return contact_id


# ── Document linking ───────────────────────────────────────────────────


def link_document_contacts(document_id: int, messages: list[dict]) -> int:
    """Link document to contacts based on message participants.

    Returns number of contacts linked.
    """
    seen_senders: dict[str, dict] = {}  # jid → msg metadata

    for msg in messages:
        if msg.get("fromMe"):
            continue  # Sebastian is implicit; skip

        sender_jid = msg.get("senderJid") or msg.get("chatJid", "")
        if sender_jid in seen_senders:
            continue

        seen_senders[sender_jid] = {
            "jid": msg.get("chatJid"),
            "phone": msg.get("phoneJid"),
            "push_name": msg.get("senderName"),
        }

    linked = 0
    for sender_jid, meta in seen_senders.items():
        contact_id = resolve_contact(
            jid=meta["jid"],
            phone=jid_to_phone(meta["phone"]) if meta["phone"] else None,
            push_name=meta["push_name"],
        )
        if contact_id:
            _link_doc_contact(document_id, contact_id, "participant")
            linked += 1

    return linked


# ── Bootstrap from historical exports ──────────────────────────────────


def bootstrap_contacts_from_exports() -> int:
    """Create contacts from 60+ historical WA export source_names.

    source_name format: '_chat Zofia Godula - partnerka od sierpnia 2023'
    Parses: canonical_name = 'Zofia Godula', notes = 'partnerka od sierpnia 2023'
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_name FROM sources
                WHERE source_type = 'whatsapp'
                  AND source_name LIKE '_chat %%'
                ORDER BY source_name
                """
            )
            rows = cur.fetchall()

    created = 0
    for (source_name,) in rows:
        name, notes = _parse_export_source_name(source_name)
        if not name:
            continue

        # Check if contact already exists by name
        existing = _find_by_exact_name(name)
        if existing:
            continue

        _create_contact(
            canonical_name=name,
            jid=None,
            phone=None,
            push_name=None,
            notes=notes,
        )
        created += 1
        logger.info("bootstrapped_contact", name=name, notes=notes[:50] if notes else None)

    logger.info("bootstrap_complete", created=created, total_exports=len(rows))
    return created


def _parse_export_source_name(source_name: str) -> tuple[str | None, str | None]:
    """Parse '_chat Name - description' → (name, description)."""
    # Remove '_chat ' prefix
    text = source_name
    if text.startswith("_chat "):
        text = text[6:]
    elif text.startswith("_chat"):
        text = text[5:]
    else:
        return None, None

    text = text.strip()
    if not text:
        return None, None

    # Handle leading dash: "- Moritz Ignat - desc" → "Moritz Ignat - desc"
    text = re.sub(r"^-\s*", "", text)

    # Handle numbered variants: "Name 2 - desc" or "Name 1- desc"
    # Strip trailing number before dash
    parts = re.split(r"\s*\d*\s*-\s*", text, maxsplit=1)
    name = parts[0].strip() if parts else text
    notes = parts[1].strip() if len(parts) > 1 else None

    # Clean name: remove leading "- " if present
    name = name.lstrip("- ").strip()

    return name if name else None, notes


# ── DB helpers ─────────────────────────────────────────────────────────


def _find_by_phone(phone: str) -> int | None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM contacts WHERE whatsapp_phone = %s LIMIT 1",
                (phone,),
            )
            row = cur.fetchone()
    return row[0] if row else None


def _find_by_jid(jid: str) -> int | None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM contacts WHERE whatsapp_jid = %s LIMIT 1",
                (jid,),
            )
            row = cur.fetchone()
    return row[0] if row else None


def _find_by_exact_name(name: str) -> int | None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM contacts WHERE canonical_name = %s LIMIT 1",
                (name,),
            )
            row = cur.fetchone()
    return row[0] if row else None


def _find_by_name_fuzzy(push_name: str) -> tuple[int | None, float]:
    """Find best fuzzy match for push_name among all contacts."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, canonical_name FROM contacts")
            rows = cur.fetchall()

    if not rows:
        return None, 0.0

    best_id = None
    best_score = 0.0

    push_lower = push_name.lower().strip()

    for contact_id, canonical in rows:
        if not canonical:
            continue
        score = SequenceMatcher(None, push_lower, canonical.lower()).ratio()
        if score > best_score:
            best_score = score
            best_id = contact_id

    return best_id, best_score


def _create_contact(
    canonical_name: str,
    jid: str | None,
    phone: str | None,
    push_name: str | None,
    notes: str | None = None,
) -> int:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contacts (canonical_name, whatsapp_jid, whatsapp_phone, whatsapp_push_name, notes)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (canonical_name, jid, phone, push_name, notes),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]


def _update_contact_jid(contact_id: int, jid: str, push_name: str | None) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE contacts
                SET whatsapp_jid = COALESCE(whatsapp_jid, %s),
                    whatsapp_push_name = COALESCE(whatsapp_push_name, %s),
                    updated_at = now()
                WHERE id = %s
                """,
                (jid, push_name, contact_id),
            )
        conn.commit()


def _link_doc_contact(document_id: int, contact_id: int, role: str) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO document_contacts (document_id, contact_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (document_id, contact_id) DO NOTHING
                """,
                (document_id, contact_id, role),
            )
        conn.commit()


def _log_match(
    contact_id: int,
    source_type: str,
    matched_field: str,
    matched_value: str,
    confidence: float,
) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contact_link_log (contact_id, source_type, matched_field, matched_value, confidence)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (contact_id, source_type, matched_field, matched_value, confidence),
            )
        conn.commit()
