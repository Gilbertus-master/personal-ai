"""
Contact Resolver — Cross-source person identity linking.

Resolves WhatsApp JIDs, email addresses, and Teams UPNs to unified
contact records. Enables cross-source entity linking for Gilbertus.

Key functions:
- resolve_wa_jid(jid) → contact_id
- link_person_across_sources(contact_id) → linked fields
- enrich_document_contacts(doc_id) → document_contacts rows
- bootstrap_contacts_from_wa_export() → initial contacts from WA history
"""

from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger("contact_resolver")

# ── Config ───────────────────────────────────────────────────────────────

WA_EXPORT_DIR = Path(
    os.environ.get("WA_EXPORT_DIR", "data/raw/whatsapp")
)

FUZZY_THRESHOLD = 0.85  # 85% similarity for name matching

SEBASTIAN_JID = "48505441635"


# ── Helpers ──────────────────────────────────────────────────────────────


def normalize_phone(phone: str | None) -> str | None:
    """Normalize phone number: strip +, spaces, dashes, parentheses."""
    if not phone:
        return None
    cleaned = re.sub(r"[\s\-\(\)\+]", "", phone)
    if not cleaned or not cleaned.isdigit():
        return None
    return cleaned


def parse_wa_jid(jid: str) -> dict:
    """Parse WhatsApp JID into components.

    Formats:
    - 48609979814@s.whatsapp.net (standard phone-based)
    - 214198726455434@lid (device-linked ID, no phone extractable)
    - 48606692917-1627993218@g.us (group)
    - 120363403273572137@g.us (group)
    """
    result = {"jid": jid, "phone": None, "is_group": False, "is_lid": False}

    if not jid:
        return result

    if jid.endswith("@g.us"):
        result["is_group"] = True
        return result

    if jid.endswith("@lid"):
        result["is_lid"] = True
        return result

    if jid.endswith("@s.whatsapp.net"):
        phone_part = jid.split("@")[0].split(":")[0]
        if phone_part.isdigit() and len(phone_part) >= 9:
            result["phone"] = phone_part
    return result


def fuzzy_match(name1: str, name2: str) -> float:
    """Compare two names using SequenceMatcher. Returns similarity ratio 0-1."""
    if not name1 or not name2:
        return 0.0
    n1 = name1.strip().lower()
    n2 = name2.strip().lower()
    if n1 == n2:
        return 1.0
    return SequenceMatcher(None, n1, n2).ratio()


def _name_parts(name: str) -> tuple[str, str]:
    """Split a name into (first, last). Handles single-word names."""
    parts = name.strip().split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return name.strip(), ""


# ── Core: resolve_wa_jid ────────────────────────────────────────────────


def resolve_wa_jid(jid: str, push_name: str | None = None, chat_name: str | None = None) -> int | None:
    """Resolve a WhatsApp JID to a contact_id.

    Looks up by JID first, then by phone number, then by push_name fuzzy match.
    Creates a new contact if no match found and we have enough info.

    Returns contact_id or None.
    """
    parsed = parse_wa_jid(jid)

    if parsed["is_group"]:
        return None  # Groups are not contacts

    # 1. Exact JID match
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM contacts WHERE whatsapp_jid = %s",
                (jid,),
            )
            row = cur.fetchone()
            if row:
                return row[0]

    # 2. Phone match (for @s.whatsapp.net JIDs)
    if parsed["phone"]:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM contacts WHERE whatsapp_phone = %s",
                    (parsed["phone"],),
                )
                row = cur.fetchone()
                if row:
                    # Update JID on existing contact
                    cur.execute(
                        "UPDATE contacts SET whatsapp_jid = %s, updated_at = NOW() WHERE id = %s",
                        (jid, row[0]),
                    )
                    conn.commit()
                    return row[0]

    # 3. Determine canonical name from available info
    canonical = push_name or chat_name
    if not canonical:
        return None

    # Skip Sebastian's own contact
    if parsed["phone"] == SEBASTIAN_JID:
        return None

    # 4. Fuzzy name match against existing contacts
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, canonical_name FROM contacts")
            for cid, cname in cur.fetchall():
                if fuzzy_match(canonical, cname) >= FUZZY_THRESHOLD:
                    # Update with WA info
                    cur.execute(
                        """UPDATE contacts
                           SET whatsapp_jid = COALESCE(whatsapp_jid, %s),
                               whatsapp_phone = COALESCE(whatsapp_phone, %s),
                               whatsapp_push_name = COALESCE(whatsapp_push_name, %s),
                               updated_at = NOW()
                           WHERE id = %s""",
                        (jid, parsed["phone"], push_name, cid),
                    )
                    conn.commit()
                    log.info("wa_jid_fuzzy_linked", contact_id=cid, jid=jid, name=canonical, matched=cname)
                    return cid

    # 5. Create new contact
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO contacts (canonical_name, whatsapp_jid, whatsapp_phone, whatsapp_push_name)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT DO NOTHING
                   RETURNING id""",
                (canonical, jid, parsed["phone"], push_name),
            )
            row = cur.fetchone()
            conn.commit()
            if row:
                log.info("wa_contact_created", contact_id=row[0], jid=jid, name=canonical)
                return row[0]

    return None


# ── Cross-source linking ────────────────────────────────────────────────


def link_person_across_sources(contact_id: int) -> dict:
    """For a given contact, find matches in email, Teams, and WA historical sources.

    Returns dict of newly linked fields.
    """
    linked = {}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT canonical_name, whatsapp_phone, email_address, teams_upn FROM contacts WHERE id = %s",
                (contact_id,),
            )
            row = cur.fetchone()
            if not row:
                return linked
            name, phone, email, teams = row

    # Try each matching strategy
    if not email:
        email = _find_email_for_contact(contact_id, name, phone)
        if email:
            linked["email_address"] = email

    if not teams:
        teams_info = _find_teams_for_contact(contact_id, name, email)
        if teams_info:
            linked.update(teams_info)

    # Apply updates
    if linked:
        _update_contact(contact_id, linked)

    return linked


def _find_email_for_contact(contact_id: int, name: str, phone: str | None) -> str | None:
    """Search email documents for matching person by name."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Search in document authors and participants from email sources
            cur.execute(
                """
                SELECT DISTINCT d.author
                FROM documents d
                JOIN sources s ON d.source_id = s.id
                WHERE s.source_type = 'email'
                  AND d.author IS NOT NULL
                  AND d.author LIKE '%%@%%'
                """,
            )
            for (author,) in cur.fetchall():
                # Extract display name from email if format is "Name <email>"
                email_addr = author.strip()
                # Try name matching against the local part
                local = email_addr.split("@")[0].replace(".", " ").replace("_", " ").replace("-", " ")
                if fuzzy_match(name, local) >= FUZZY_THRESHOLD:
                    _log_link(contact_id, "email", "name_fuzzy", email_addr, fuzzy_match(name, local))
                    return email_addr

            # Search in participants JSON arrays
            cur.execute(
                """
                SELECT DISTINCT p.participant
                FROM documents d
                JOIN sources s ON d.source_id = s.id,
                jsonb_array_elements_text(d.participants) AS p(participant)
                WHERE s.source_type = 'email'
                  AND p.participant LIKE '%%@%%'
                """,
            )
            for (participant,) in cur.fetchall():
                local = participant.split("@")[0].replace(".", " ").replace("_", " ").replace("-", " ")
                if fuzzy_match(name, local) >= FUZZY_THRESHOLD:
                    _log_link(contact_id, "email", "name_fuzzy", participant, fuzzy_match(name, local))
                    return participant

    return None


def _find_teams_for_contact(contact_id: int, name: str, email: str | None) -> dict | None:
    """Search Teams documents for matching person."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Search Teams participants by name
            cur.execute(
                """
                SELECT DISTINCT p.participant
                FROM documents d
                JOIN sources s ON d.source_id = s.id,
                jsonb_array_elements_text(d.participants) AS p(participant)
                WHERE s.source_type = 'teams'
                """,
            )
            for (participant,) in cur.fetchall():
                sim = fuzzy_match(name, participant)
                if sim >= FUZZY_THRESHOLD:
                    _log_link(contact_id, "teams", "name_fuzzy", participant, sim)
                    return {"teams_display_name": participant}

    return None


def _update_contact(contact_id: int, fields: dict) -> None:
    """Update contact with new fields (only non-null). Skips on unique constraint violations."""
    set_parts = []
    values = []
    for key, val in fields.items():
        if val is not None:
            set_parts.append(f"{key} = %s")
            values.append(val)
    if not set_parts:
        return
    set_parts.append("updated_at = NOW()")
    values.append(contact_id)

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE contacts SET {', '.join(set_parts)} WHERE id = %s",
                    values,
                )
            conn.commit()
        log.info("contact_updated", contact_id=contact_id, fields=list(fields.keys()))
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            log.warning("contact_update_skipped_duplicate", contact_id=contact_id, error=str(e))
        else:
            raise


def _log_link(contact_id: int, source_type: str, matched_field: str, matched_value: str, confidence: float) -> None:
    """Log a cross-source link for audit."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO contact_link_log (contact_id, source_type, matched_field, matched_value, confidence)
                   VALUES (%s, %s, %s, %s, %s)""",
                (contact_id, source_type, matched_field, matched_value, confidence),
            )
        conn.commit()


# ── Document → Contact enrichment ───────────────────────────────────────


def enrich_document_contacts(doc_id: int) -> int:
    """For a document, identify participants and link to contacts.

    Returns number of contact links created.
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT d.participants, d.author, s.source_type, d.raw_path
                   FROM documents d
                   JOIN sources s ON d.source_id = s.id
                   WHERE d.id = %s""",
                (doc_id,),
            )
            row = cur.fetchone()
            if not row:
                return 0
            participants_json, author, source_type, raw_path = row

    links_created = 0
    participants = participants_json if isinstance(participants_json, list) else (json.loads(participants_json) if participants_json else [])

    # For WA live docs, extract JID from raw_path
    if source_type == "whatsapp_live" and raw_path:
        # raw_path format: whatsapp_live://chatJid/date
        match = re.match(r"whatsapp_live://(.+)/\d{4}-\d{2}-\d{2}", raw_path)
        if match:
            chat_jid = match.group(1)
            for participant_name in participants:
                if participant_name == "Sebastian":
                    continue
                contact_id = resolve_wa_jid(chat_jid, push_name=participant_name)
                if contact_id:
                    links_created += _insert_doc_contact(doc_id, contact_id, "participant")

    # For all source types, try to match participants by name
    for participant_name in participants:
        if participant_name == "Sebastian":
            continue
        contact_id = _find_contact_by_name(participant_name)
        if contact_id:
            links_created += _insert_doc_contact(doc_id, contact_id, "participant")

    # Author
    if author and author != "multiple" and author != "Sebastian":
        contact_id = _find_contact_by_name(author)
        if contact_id:
            links_created += _insert_doc_contact(doc_id, contact_id, "sender")

    return links_created


def _find_contact_by_name(name: str) -> int | None:
    """Find a contact by exact or fuzzy name match."""
    if not name or name in ("Sebastian", "multiple"):
        return None

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Exact match first
            cur.execute(
                "SELECT id FROM contacts WHERE canonical_name = %s LIMIT 1",
                (name,),
            )
            row = cur.fetchone()
            if row:
                return row[0]

            # Fuzzy match
            cur.execute("SELECT id, canonical_name FROM contacts")
            for cid, cname in cur.fetchall():
                if fuzzy_match(name, cname) >= FUZZY_THRESHOLD:
                    return cid

    return None


def _insert_doc_contact(doc_id: int, contact_id: int, role: str) -> int:
    """Insert document_contact link. Returns 1 if inserted, 0 if existed."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO document_contacts (document_id, contact_id, role)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (document_id, contact_id) DO NOTHING""",
                    (doc_id, contact_id, role),
                )
            conn.commit()
            return 1
    except Exception:
        return 0


# ── Bootstrapper: WA export files ───────────────────────────────────────


def bootstrap_contacts_from_wa_export() -> dict:
    """Bootstrap contacts from WhatsApp historical export files.

    Scans data/raw/whatsapp/ for chat files and extracts:
    - Person name from filename
    - Relationship description from filename
    - Phone number if present in filename or content

    Returns stats dict.
    """
    stats = {"files_scanned": 0, "contacts_created": 0, "contacts_existing": 0}

    if not WA_EXPORT_DIR.exists():
        log.warning("wa_export_dir_missing", path=str(WA_EXPORT_DIR))
        return stats

    for f in sorted(WA_EXPORT_DIR.iterdir()):
        if not f.name.endswith(".txt"):
            continue

        stats["files_scanned"] += 1

        # Parse filename: "_chat Name - description.txt"
        name_info = _parse_wa_filename(f.name)
        if not name_info:
            continue

        canonical_name = name_info["name"]
        notes = name_info.get("description", "")

        # Try to find phone from file content (first few lines)
        phone = _extract_phone_from_wa_file(f)

        # Create or skip
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO contacts (canonical_name, whatsapp_phone, notes)
                       VALUES (%s, %s, %s)
                       ON CONFLICT DO NOTHING
                       RETURNING id""",
                    (canonical_name, phone, notes if notes else None),
                )
                row = cur.fetchone()
                conn.commit()
                if row:
                    stats["contacts_created"] += 1
                    log.info(
                        "wa_bootstrap_contact",
                        contact_id=row[0],
                        name=canonical_name,
                        phone=phone,
                    )
                else:
                    stats["contacts_existing"] += 1

    log.info("wa_bootstrap_complete", **stats)
    return stats


def _parse_wa_filename(filename: str) -> dict | None:
    """Parse WA export filename into name + description.

    Formats:
    - "_chat Name - description.txt"
    - "_chat Name.txt"
    """
    # Remove extension
    base = filename.rsplit(".txt", 1)[0]

    # Remove _chat prefix and leading whitespace/dashes
    if base.startswith("_chat "):
        base = base[6:]
    elif base.startswith("_chat"):
        base = base[5:]
    else:
        return None

    # Remove leading "- " if present
    base = base.lstrip("- ").strip()

    # Split on " - " for name/description
    if " - " in base:
        parts = base.split(" - ", 1)
        name = parts[0].strip()
        desc = parts[1].strip()
    else:
        name = base.strip()
        desc = ""

    if not name:
        return None

    # Handle numbered duplicates: "Name 2 description" where description contains name info
    # Only strip trailing number if it's clearly a duplicate marker
    if re.match(r"^.+ \d$", name):
        name = name.rsplit(" ", 1)[0]

    return {"name": name, "description": desc}


def _extract_phone_from_wa_file(filepath: Path) -> str | None:
    """Try to extract phone number from first few lines of WA export file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for _ in range(20):
                line = f.readline()
                if not line:
                    break
                # Look for phone patterns: +48 XXX XXX XXX or similar
                match = re.search(r"\+?(\d{2,3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{3})", line)
                if match:
                    return normalize_phone(match.group(0))
    except Exception:
        pass
    return None


# ── Bulk operations ─────────────────────────────────────────────────────


def link_all_contacts() -> dict:
    """Run cross-source linking for all contacts. Returns stats."""
    stats = {"total": 0, "linked": 0}
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM contacts ORDER BY id")
            contact_ids = [r[0] for r in cur.fetchall()]

    stats["total"] = len(contact_ids)
    for cid in contact_ids:
        result = link_person_across_sources(cid)
        if result:
            stats["linked"] += 1

    log.info("link_all_complete", **stats)
    return stats


def enrich_all_documents(source_type: str | None = None) -> dict:
    """Enrich all documents with contact links. Returns stats."""
    stats = {"total": 0, "enriched": 0, "links_created": 0}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if source_type:
                cur.execute(
                    """SELECT d.id FROM documents d
                       JOIN sources s ON d.source_id = s.id
                       WHERE s.source_type = %s
                       ORDER BY d.id""",
                    (source_type,),
                )
            else:
                cur.execute("SELECT id FROM documents ORDER BY id")
            doc_ids = [r[0] for r in cur.fetchall()]

    stats["total"] = len(doc_ids)
    for did in doc_ids:
        links = enrich_document_contacts(did)
        if links > 0:
            stats["enriched"] += 1
            stats["links_created"] += links

    log.info("enrich_all_complete", source_type=source_type, **stats)
    return stats
