"""
WhatsApp Live Importer for Gilbertus Albans.

Reads the JSONL file produced by the Baileys listener (listener.js) and
imports new messages into the Gilbertus database.

Messages are grouped by chat+day into documents, then chunked.  A state
file tracks the last-processed line so we never re-import.

Designed to run as cron every 5 minutes:
    python -m app.ingestion.whatsapp_live.importer

Source type: whatsapp_live
Raw path format: whatsapp_live://<chatJid>/<date>
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.db.postgres import get_pg_connection
from app.ingestion.common.db import (
    insert_chunk,
    insert_document,
    insert_source,
)

# ── Config ───────────────────────────────────────────────────────────────

MESSAGES_FILE = Path(
    os.environ.get(
        "WA_MESSAGES_FILE",
        os.path.expanduser("~/.gilbertus/whatsapp_listener/messages.jsonl"),
    )
)

STATE_FILE = Path(
    os.environ.get(
        "WA_IMPORTER_STATE",
        os.path.expanduser("~/.gilbertus/whatsapp_listener/importer_state.json"),
    )
)

CHUNK_TARGET = 3000
CHUNK_OVERLAP = 300

MY_JID = "48505441635"  # Sebastian's WhatsApp number

# Skip self-chat messages (already captured by OpenClaw / live_ingest.py)
SKIP_SELF_CHAT = True

# ── State management ────────────────────────────────────────────────────


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_offset": 0, "imported_docs": {}}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ── Text chunking ───────────────────────────────────────────────────────


def chunk_text(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_TARGET, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


# ── Message reading ─────────────────────────────────────────────────────


def read_new_messages(offset: int) -> tuple[list[dict], int]:
    """Read messages from JSONL file starting at byte offset.

    Returns (messages, new_offset).
    """
    if not MESSAGES_FILE.exists():
        return [], offset

    messages = []
    new_offset = offset

    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        f.seek(offset)
        while True:
            line = f.readline()
            if not line:
                break
            new_offset = f.tell()
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                messages.append(msg)
            except json.JSONDecodeError:
                continue

    return messages, new_offset


# ── Grouping ────────────────────────────────────────────────────────────


def group_messages_by_chat_day(
    messages: list[dict],
) -> dict[str, list[dict]]:
    """Group messages by (chatJid, date) into buckets.

    Key format: chatJid/YYYY-MM-DD
    """
    groups: dict[str, list[dict]] = defaultdict(list)

    for msg in messages:
        chat_jid = msg.get("chatJid", "unknown")

        # Skip self-chat if configured
        if SKIP_SELF_CHAT:
            if not msg.get("isGroup") and chat_jid.startswith(f"{MY_JID}@"):
                continue

        ts = msg.get("timestamp", 0)
        if ts > 1e12:
            ts = ts / 1000  # ms -> s
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OSError, ValueError):
            dt = datetime.now(tz=timezone.utc)

        date_str = dt.strftime("%Y-%m-%d")
        key = f"{chat_jid}/{date_str}"
        msg["_dt"] = dt
        groups[key].append(msg)

    return dict(groups)


# ── Formatting ──────────────────────────────────────────────────────────


def format_sender(msg: dict) -> str:
    """Human-readable sender name."""
    if msg.get("fromMe"):
        return "Sebastian"
    name = msg.get("senderName")
    if name:
        return name
    sender = msg.get("senderJid", "?")
    return f"+{sender}" if sender and sender[0].isdigit() else sender


def format_message_line(msg: dict) -> str:
    dt = msg.get("_dt", datetime.now(tz=timezone.utc))
    sender = format_sender(msg)
    body = msg.get("body", "")
    return f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] {sender}: {body}"


def build_document_text(chat_name: str, date_str: str, messages: list[dict]) -> str:
    """Build full document text for a chat+day group."""
    header = f"WhatsApp — {chat_name} — {date_str}"
    is_group = messages[0].get("isGroup", False) if messages else False
    if is_group:
        header += " (grupa)"

    lines = [header, ""]
    for msg in sorted(messages, key=lambda m: m.get("timestamp", 0)):
        lines.append(format_message_line(msg))

    return "\n".join(lines)


# ── Import logic ────────────────────────────────────────────────────────


def ensure_source() -> int:
    """Get or create the whatsapp_live source."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM sources WHERE source_type = %s AND source_name = %s LIMIT 1",
                ("whatsapp_live", "whatsapp_all_chats"),
            )
            rows = cur.fetchall()
            if rows:
                return rows[0][0]

    return insert_source(
        conn=None,
        source_type="whatsapp_live",
        source_name="whatsapp_all_chats",
    )


def import_group(
    source_id: int,
    key: str,
    messages: list[dict],
    existing_docs: dict[str, int],
) -> tuple[int, int]:
    """Import or update a chat+day group.

    Returns (docs_imported, chunks_created).
    """
    chat_jid, date_str = key.rsplit("/", 1)
    raw_path = f"whatsapp_live://{key}"

    chat_name = messages[0].get("chatName", chat_jid) if messages else chat_jid

    # Build the full text
    full_text = build_document_text(chat_name, date_str, messages)
    if len(full_text) < 30:
        return 0, 0

    # Collect participants
    participants = sorted(
        {format_sender(m) for m in messages}
    )

    # Timestamps
    sorted_msgs = sorted(messages, key=lambda m: m.get("timestamp", 0))
    first_dt = sorted_msgs[0].get("_dt")
    last_dt = sorted_msgs[-1].get("_dt")

    doc_id = existing_docs.get(raw_path)

    if doc_id:
        # Document exists — delete old chunks and re-create with updated text
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
            conn.commit()

        # Update document metadata
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE documents
                    SET title = %s, created_at = %s, participants = %s::jsonb
                    WHERE id = %s
                    """,
                    (
                        f"WhatsApp {chat_name} {date_str}",
                        first_dt.isoformat() if first_dt else None,
                        json.dumps(participants, ensure_ascii=False),
                        doc_id,
                    ),
                )
            conn.commit()
    else:
        # New document
        is_group = messages[0].get("isGroup", False) if messages else False
        title = f"WhatsApp {chat_name} {date_str}"
        if is_group:
            title = f"WhatsApp grupa {chat_name} {date_str}"

        doc_id = insert_document(
            conn=None,
            source_id=source_id,
            title=title,
            created_at=first_dt,
            author="multiple" if len(participants) > 1 else participants[0] if participants else None,
            participants=participants,
            raw_path=raw_path,
        )

    # Insert chunks
    chunks = chunk_text(full_text)
    for ci, chunk in enumerate(chunks):
        insert_chunk(
            conn=None,
            document_id=doc_id,
            chunk_index=ci,
            text=chunk,
            timestamp_start=first_dt,
            timestamp_end=last_dt,
            embedding_id=None,
        )

    return 1, len(chunks)


# ── Existing document lookup ────────────────────────────────────────────


def load_existing_docs() -> dict[str, int]:
    """Load raw_path -> document_id for all whatsapp_live documents."""
    result = {}
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id, d.raw_path
                FROM documents d
                JOIN sources s ON d.source_id = s.id
                WHERE s.source_type = 'whatsapp_live'
                  AND d.raw_path LIKE 'whatsapp_live://%%'
                """
            )
            for row in cur.fetchall():
                result[row[1]] = row[0]
    return result


# ── Main ────────────────────────────────────────────────────────────────


def run() -> None:
    state = load_state()
    offset = state.get("last_offset", 0)

    messages, new_offset = read_new_messages(offset)

    if not messages:
        print(f"[{datetime.now(tz=timezone.utc).strftime('%H:%M')}] WhatsApp live: no new messages")
        return

    print(
        f"[{datetime.now(tz=timezone.utc).strftime('%H:%M')}] WhatsApp live: {len(messages)} new messages"
    )

    # Group by chat+day
    groups = group_messages_by_chat_day(messages)
    if not groups:
        print("  All messages filtered (self-chat only)")
        state["last_offset"] = new_offset
        save_state(state)
        return

    source_id = ensure_source()
    existing_docs = load_existing_docs()

    total_docs = 0
    total_chunks = 0

    for key, msgs in groups.items():
        # For existing documents, we need to re-read ALL messages for that
        # chat+day to build a complete document (not just the new ones).
        # Load previously imported messages for this key if doc already exists.
        raw_path = f"whatsapp_live://{key}"
        if raw_path in existing_docs:
            # Re-read all messages for this chat+day from the JSONL
            all_msgs_for_key = _read_all_messages_for_key(key)
            # Merge: old messages + new messages (deduplicate by id)
            seen_ids = {m.get("id") for m in all_msgs_for_key if m.get("id")}
            for m in msgs:
                if m.get("id") not in seen_ids:
                    all_msgs_for_key.append(m)
            msgs = all_msgs_for_key

        docs, chunks = import_group(source_id, key, msgs, existing_docs)
        total_docs += docs
        total_chunks += chunks

    # Save state
    state["last_offset"] = new_offset
    save_state(state)

    print(f"  Imported: {total_docs} documents, {total_chunks} chunks")
    print(f"  Chats touched: {list(groups.keys())}")


def _read_all_messages_for_key(key: str) -> list[dict]:
    """Read ALL messages from the JSONL file matching a specific chat+day key.

    This is needed when updating an existing document — we need the full
    conversation, not just the new messages.
    """
    chat_jid, date_str = key.rsplit("/", 1)
    result = []

    if not MESSAGES_FILE.exists():
        return result

    with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            if msg.get("chatJid") != chat_jid:
                continue

            ts = msg.get("timestamp", 0)
            if ts > 1e12:
                ts = ts / 1000
            try:
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            except (OSError, ValueError):
                continue

            if dt.strftime("%Y-%m-%d") == date_str:
                msg["_dt"] = dt
                result.append(msg)

    return result


def main() -> None:
    run()


if __name__ == "__main__":
    main()
