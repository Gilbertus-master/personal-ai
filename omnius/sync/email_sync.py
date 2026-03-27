"""Sync email from M365 mailboxes into Omnius documents/chunks.

Uses Microsoft Graph API with application permissions to read mail
from configured mailboxes. Classifies emails based on sender/recipient.
"""
from __future__ import annotations

import structlog
from datetime import datetime, timezone, timedelta

from omnius.db.postgres import get_pg_connection
from omnius.sync.graph_api import graph_get_all

log = structlog.get_logger(__name__)

# Mailboxes to sync (configured via omnius_config or env)
DEFAULT_MAILBOXES = [
    "krystian@re-fuels.com",
    "edgar.mikolajek@re-fuels.com",
    "witold.pawlowski@re-fuels.com",
]


def sync_emails(hours: int = 24, mailboxes: list[str] | None = None) -> dict:
    """Sync emails from M365 mailboxes for the last N hours."""
    if mailboxes is None:
        mailboxes = _load_mailboxes()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    stats = {"mailboxes": len(mailboxes), "emails_found": 0, "synced": 0, "skipped": 0}

    for mailbox in mailboxes:
        try:
            messages = graph_get_all(
                f"/users/{mailbox}/messages",
                params={
                    "$filter": f"receivedDateTime gt {cutoff_iso}",
                    "$select": "id,subject,bodyPreview,body,from,toRecipients,"
                               "ccRecipients,receivedDateTime,hasAttachments,importance",
                    "$top": "50",
                    "$orderby": "receivedDateTime desc",
                },
                max_pages=5,
            )

            stats["emails_found"] += len(messages)

            for msg in messages:
                msg_id = msg.get("id", "")
                source_id = f"email:{mailbox}:{msg_id}"

                # Dedup
                with get_pg_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM omnius_documents WHERE source_id = %s", (source_id,))
                        if cur.fetchone():
                            stats["skipped"] += 1
                            continue

                subject = msg.get("subject", "(brak tematu)")
                body_content = (msg.get("body", {}).get("content") or
                                msg.get("bodyPreview") or "").strip()

                if not body_content or len(body_content) < 20:
                    stats["skipped"] += 1
                    continue

                # Strip HTML tags (simple)
                import re
                body_text = re.sub(r'<[^>]+>', '', body_content)
                body_text = re.sub(r'\s+', ' ', body_text).strip()

                sender = (msg.get("from", {}).get("emailAddress", {}).get("address") or "unknown")
                sender_name = (msg.get("from", {}).get("emailAddress", {}).get("name") or sender)
                recipients = [r.get("emailAddress", {}).get("address", "")
                              for r in msg.get("toRecipients", [])]
                cc = [r.get("emailAddress", {}).get("address", "")
                      for r in msg.get("ccRecipients", [])]
                received = msg.get("receivedDateTime", "")
                importance = msg.get("importance", "normal")

                # Build document content
                content = (
                    f"Email: {subject}\n"
                    f"Od: {sender_name} <{sender}>\n"
                    f"Do: {', '.join(recipients)}\n"
                    f"{'CC: ' + ', '.join(cc) if cc else ''}\n"
                    f"Data: {received}\n"
                    f"Ważność: {importance}\n\n"
                    f"{body_text[:10000]}"
                )

                # Classify
                classification = _classify_email(subject, sender, importance)

                _insert_email(
                    source_id=source_id,
                    title=f"[Email] {subject}",
                    content=content,
                    classification=classification,
                    received_at=received,
                    department=_infer_department(sender, recipients),
                )
                stats["synced"] += 1

        except Exception as e:
            log.error("email_sync_failed", mailbox=mailbox, error=str(e))
            stats[f"error_{mailbox}"] = str(e)

    log.info("email_sync_complete", **stats)
    return stats


def _classify_email(subject: str, sender: str, importance: str) -> str:
    """Classify email based on content signals."""
    subject_lower = subject.lower()

    if any(kw in subject_lower for kw in ("poufne", "confidential", "board", "zarząd")):
        return "confidential"
    if any(kw in subject_lower for kw in ("ceo", "prezes", "personal")):
        return "ceo_only"
    if importance == "high":
        return "confidential"

    return "internal"


def _infer_department(sender: str, recipients: list[str]) -> str | None:
    """Try to infer department from email addresses."""
    all_addresses = [sender] + recipients
    for addr in all_addresses:
        addr_lower = addr.lower()
        if "trading" in addr_lower or "handel" in addr_lower:
            return "trading"
        if "finance" in addr_lower or "finanse" in addr_lower:
            return "finance"
        if "hr" in addr_lower or "kadry" in addr_lower:
            return "hr"
        if "it" in addr_lower or "tech" in addr_lower:
            return "it"
    return None


def _load_mailboxes() -> list[str]:
    """Load mailbox list from config or defaults."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM omnius_config WHERE key = 'sync:email:mailboxes'")
                row = cur.fetchone()
                if row:
                    import json
                    return json.loads(row[0]) if isinstance(row[0], str) else row[0]
    except Exception:
        pass
    return DEFAULT_MAILBOXES


def _insert_email(source_id: str, title: str, content: str,
                   classification: str, received_at: str, department: str | None):
    """Insert email document + chunks."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO omnius_documents
                    (source_type, source_id, title, content, classification, department,
                     imported_at)
                VALUES ('email', %s, %s, %s, %s, %s,
                        COALESCE(%s::timestamptz, NOW()))
                ON CONFLICT (source_id) DO NOTHING
                RETURNING id
            """, (source_id, title, content[:500], classification, department, received_at))
            row = cur.fetchone()
            if not row:
                return

            doc_id = row[0]

            # Chunk email (2000 chars for emails — shorter than audio)
            chunk_size = 2000
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size].strip()
                if len(chunk) < 20:
                    continue
                cur.execute("""
                    INSERT INTO omnius_chunks (document_id, content, classification)
                    VALUES (%s, %s, %s)
                """, (doc_id, chunk, classification))
        conn.commit()
