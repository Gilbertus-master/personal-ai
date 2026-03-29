#!/usr/bin/env python3
"""
Group Teams messages into conversation documents.

Takes individual Teams message chunks and merges them into conversation blocks
per chat per 2-hour time window. This dramatically improves retrieval quality
by providing conversation context instead of isolated messages.

Run: .venv/bin/python scripts/group_teams_messages.py [--dry-run]

Flow:
1. For each Teams chat, group messages within 2h windows
2. Create new conversation documents with merged text
3. Mark merged chunks for re-embedding
4. Delete old individual message docs+chunks
5. Add text_hash to prevent future dupes
"""
import structlog
import hashlib
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

log = structlog.get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DRY_RUN = "--dry-run" in sys.argv
WINDOW_HOURS = 4
CHUNK_TARGET = 3000


def get_conn():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "gilbertus"),
        user=os.getenv("POSTGRES_USER", "gilbertus"),
        password=os.getenv("POSTGRES_PASSWORD", "gilbertus"),
    )


def extract_chat_id(raw_path: str, title: str) -> str:
    """Extract chat/channel grouping key.

    Graph API: 'graph://teams/CHAT_ID/MSG_ID' → CHAT_ID
    PST export: group by channel name (e.g. "HANDEL WŁASNY_609" → "HANDEL WŁASNY")
    Short PST titles (1:1 chats): group by "oneOnOne" catch-all
    """
    import re

    if raw_path and raw_path.startswith("graph://teams/"):
        parts = raw_path.replace("graph://teams/", "").split("/")
        return f"graph_{parts[0]}" if parts else f"title_{title}"

    # PST: extract channel name from title or filename
    # Patterns: "HANDEL WŁASNY_609", "EFETY_470", "hej_902", "Traders_87"
    clean_title = re.sub(r'_\d+$', '', title or 'unknown').strip()

    # Known channel names (capitalized, multi-word) → group together
    # Short generic titles (hej, ok, dzieki, nom) = 1:1 chats → group into "oneOnOne_firstword"
    KNOWN_CHANNELS = [
        "HANDEL WŁASNY", "EFETY", "EEX", "UZGADNIANIE KSIĄŻEK", "Traders",
        "Portfolio Management", "Forum Romanum", "Weather Cat", "IRGIT",
        "PM OTC", "MB Group", "Asset Optimazation",
    ]

    for channel in KNOWN_CHANNELS:
        if clean_title.startswith(channel):
            return f"pst_channel_{channel}"

    # 1:1 chats and misc — group by first word (lowercase) to batch similar short messages
    first_word = clean_title.split()[0].lower() if clean_title else "unknown"
    if len(clean_title) < 30:
        return f"pst_chat_{first_word}"

    # Long unique titles = standalone threads, keep separate
    return f"pst_thread_{clean_title[:50]}"


def group_messages_into_windows(messages: list[dict], window_hours: int = 2) -> list[list[dict]]:
    """Group messages into time windows."""
    if not messages:
        return []

    # Sort by timestamp
    messages.sort(key=lambda m: m["created_at"] or datetime.min.replace(tzinfo=timezone.utc))

    windows = []
    current_window = [messages[0]]
    window_start = messages[0]["created_at"]

    for msg in messages[1:]:
        msg_time = msg["created_at"]
        if msg_time and window_start and (msg_time - window_start) < timedelta(hours=window_hours):
            current_window.append(msg)
        else:
            windows.append(current_window)
            current_window = [msg]
            window_start = msg_time

    if current_window:
        windows.append(current_window)

    return windows


def merge_window_text(messages: list[dict]) -> str:
    """Merge messages into a single conversation text."""
    lines = []
    for msg in messages:
        ts = msg["created_at"].strftime("%Y-%m-%d %H:%M") if msg["created_at"] else "?"
        lines.append(f"[{ts}] {msg['text']}")
    return "\n".join(lines)


def chunk_text(text: str, target: int = CHUNK_TARGET, overlap: int = 300) -> list[str]:
    """Split text into chunks if it exceeds target size."""
    if len(text) <= target:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + target
        # Try to break at newline
        if end < len(text):
            newline_pos = text.rfind("\n", start + target // 2, end)
            if newline_pos > start:
                end = newline_pos + 1
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]


def main():
    conn = get_conn()
    cur = conn.cursor()

    # Step 0: Count before
    cur.execute("""
        SELECT COUNT(DISTINCT d.id) as docs, COUNT(c.id) as chunks
        FROM documents d
        JOIN chunks c ON c.document_id = d.id
        JOIN sources s ON d.source_id = s.id
        WHERE s.source_type = 'teams'
    """)
    docs_before, chunks_before = cur.fetchone()
    log.info(f"=== BEFORE: {docs_before} docs, {chunks_before} chunks (Teams) ===")

    if DRY_RUN:
        log.info("[DRY RUN] No changes will be made.\n")

    # Step 1: Fetch all Teams messages with chat context (both Graph API and PST)
    log.info("Step 1: Fetching all Teams messages...")
    cur.execute("""
        SELECT d.id as doc_id, d.title, d.created_at, d.author, d.raw_path,
               c.id as chunk_id, c.text, c.timestamp_start,
               s.id as source_id
        FROM documents d
        JOIN chunks c ON c.document_id = d.id
        JOIN sources s ON d.source_id = s.id
        WHERE s.source_type = 'teams'
        ORDER BY d.created_at
    """)
    rows = cur.fetchall()
    log.info(f"  Found {len(rows)} Teams message chunks")

    if not rows:
        log.info("No Teams messages to group.")
        conn.close()
        return

    # Step 2: Group by chat_id
    log.info("Step 2: Grouping by chat...")
    chats = defaultdict(list)
    source_id = rows[0][8]

    for row in rows:
        doc_id, title, created_at, author, raw_path, chunk_id, text, ts_start, src_id = row
        chat_id = extract_chat_id(raw_path, title)
        chats[chat_id].append({
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "title": title,
            "created_at": created_at or ts_start,
            "author": author,
            "text": text,
            "raw_path": raw_path,
        })

    log.info(f"  {len(chats)} unique chats")

    # Step 3: Group into windows and create new docs
    log.info("Step 3: Creating conversation documents...")
    new_docs = 0
    new_chunks = 0
    old_doc_ids = set()
    old_chunk_ids = set()

    for chat_id, messages in chats.items():
        # Skip chats with <=3 messages — already fine as individual docs
        if len(messages) <= 3:
            continue

        # Collect old IDs for deletion
        for msg in messages:
            old_doc_ids.add(msg["doc_id"])
            old_chunk_ids.add(msg["chunk_id"])

        windows = group_messages_into_windows(messages, WINDOW_HOURS)
        chat_title = messages[0]["title"] if messages else f"Teams: {chat_id[:12]}"

        for window in windows:
            if not window:
                continue

            merged_text = merge_window_text(window)
            if len(merged_text) < 20:
                continue

            window_start = window[0]["created_at"]
            window_end = window[-1]["created_at"]
            participants = list(set(m["author"] for m in window if m["author"]))

            # Create conversation raw_path
            ts_str = window_start.strftime("%Y%m%d_%H%M") if window_start else "unknown"
            conv_raw_path = f"graph://teams_conv/{chat_id}/{ts_str}"

            if not DRY_RUN:
                # Insert new conversation document
                cur.execute("""
                    INSERT INTO documents (source_id, title, created_at, author, participants, raw_path)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    RETURNING id
                """, (
                    source_id,
                    f"{chat_title} ({window_start.strftime('%Y-%m-%d %H:%M') if window_start else '?'})",
                    window_start,
                    ", ".join(participants[:3]),
                    f'[{",".join(f""""{p}\"""" for p in participants)}]',
                    conv_raw_path,
                ))
                new_doc_id = cur.fetchone()[0]

                # Chunk the merged text
                text_chunks = chunk_text(merged_text)
                for idx, chunk_text_piece in enumerate(text_chunks):
                    piece_hash = hashlib.md5(chunk_text_piece.encode()).hexdigest()
                    cur.execute("""
                        INSERT INTO chunks (document_id, chunk_index, text, timestamp_start, timestamp_end,
                                           embedding_status, text_hash)
                        VALUES (%s, %s, %s, %s, %s, 'pending', %s)
                        ON CONFLICT (document_id, text_hash) DO NOTHING
                    """, (new_doc_id, idx, chunk_text_piece, window_start, window_end, piece_hash))
                    new_chunks += 1

            new_docs += 1

    log.info(f"  Created {new_docs} conversation docs, {new_chunks} chunks")
    log.info(f"  Old: {len(old_doc_ids)} docs, {len(old_chunk_ids)} chunks to delete")

    # Step 4: Migrate events and entities from old chunks to best-matching new chunks
    log.info("Step 4: Migrating events and entities...")

    if not DRY_RUN:
        # For events on old chunks: find the new conversation chunk that contains the same time window
        # Simplest approach: delete events on old chunks (they'll be re-extracted from the better conversation chunks)
        cur.execute("""
            DELETE FROM chunk_entities WHERE chunk_id = ANY(%s::bigint[])
        """, (list(old_chunk_ids),))
        ce_deleted = cur.rowcount

        cur.execute("""
            DELETE FROM events WHERE chunk_id = ANY(%s::bigint[])
        """, (list(old_chunk_ids),))
        ev_deleted = cur.rowcount

        cur.execute("""
            DELETE FROM chunks_event_checked WHERE chunk_id = ANY(%s::bigint[])
        """, (list(old_chunk_ids),))
        cur.execute("""
            DELETE FROM chunks_entity_checked WHERE chunk_id = ANY(%s::bigint[])
        """, (list(old_chunk_ids),))

        log.info(f"  Cleared {ev_deleted} events, {ce_deleted} chunk_entities (will re-extract from conversations)")

    # Step 5: Delete old individual message docs + chunks
    log.info("Step 5: Deleting old individual message docs...")

    if not DRY_RUN:
        # Chunks CASCADE from documents, but be explicit
        cur.execute("DELETE FROM chunks WHERE id = ANY(%s::bigint[])", (list(old_chunk_ids),))
        chunks_deleted = cur.rowcount
        cur.execute("DELETE FROM documents WHERE id = ANY(%s::bigint[])", (list(old_doc_ids),))
        docs_deleted = cur.rowcount
        log.info(f"  Deleted {docs_deleted} old docs, {chunks_deleted} old chunks")

    # Step 6: Final counts
    cur.execute("""
        SELECT COUNT(DISTINCT d.id) as docs, COUNT(c.id) as chunks
        FROM documents d
        JOIN chunks c ON c.document_id = d.id
        JOIN sources s ON d.source_id = s.id
        WHERE s.source_type = 'teams'
    """)
    docs_after, chunks_after = cur.fetchone()

    log.info(f"\n=== AFTER: {docs_after} docs, {chunks_after} chunks (Teams) ===")
    log.info(f"  Reduction: {docs_before} → {docs_after} docs ({docs_before - docs_after} fewer)")
    log.info(f"  Reduction: {chunks_before} → {chunks_after} chunks ({chunks_before - chunks_after} fewer)")

    if DRY_RUN:
        log.info("\n[DRY RUN] Rolling back.")
        conn.rollback()
    else:
        log.info("\n[COMMIT] Saving...")
        conn.commit()
        log.info("Done! New conversation chunks need embedding (status=pending).")

    conn.close()


if __name__ == "__main__":
    main()
