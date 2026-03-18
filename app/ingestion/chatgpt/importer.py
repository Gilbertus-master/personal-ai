import sys
from pathlib import Path

from app.ingestion.common.db import (
    document_exists_by_raw_path,
    get_connection,
    insert_chunk,
    insert_document,
    insert_source,
)
from app.ingestion.chatgpt.parser import parse_chatgpt_export_file


CHUNK_TARGET_CHARS = 5000


def build_chunk_text(messages) -> str:
    parts = []
    for msg in messages:
        ts = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S") if msg.timestamp else "unknown"
        parts.append(f"[{ts}] {msg.author}: {msg.text}")
    return "\n".join(parts)


def chunk_messages(messages):
    chunks = []
    current = []
    current_len = 0

    for msg in messages:
        ts = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S") if msg.timestamp else "unknown"
        line = f"[{ts}] {msg.author}: {msg.text}"
        line_len = len(line) + 1

        if current and current_len + line_len > CHUNK_TARGET_CHARS:
            chunks.append(current)
            current = []
            current_len = 0

        current.append(msg)
        current_len += line_len

    if current:
        chunks.append(current)

    return chunks


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.ingestion.chatgpt.importer <path_to_conversations_file.json>")
        sys.exit(1)

    file_path = Path(sys.argv[1])

    conversations = parse_chatgpt_export_file(file_path)

    if not conversations:
        print("No conversations parsed.")
        sys.exit(1)

    conn = get_connection()

    imported = 0
    skipped = 0

    for conv in conversations:
        raw_path = f"{file_path}::{conv.conversation_id}"

        if document_exists_by_raw_path(raw_path):
            print(f"Skipping already imported conversation: {conv.title}")
            skipped += 1
            continue

        source_id = insert_source(
            conn=conn,
            source_type="chatgpt",
            source_name=file_path.name,
        )

        document_id = insert_document(
            conn=conn,
            source_id=source_id,
            title=conv.title,
            created_at=conv.created_at or conv.messages[0].timestamp,
            author="multiple",
            participants=["user", "assistant"],
            raw_path=raw_path,
        )

        grouped_chunks = chunk_messages(conv.messages)

        for idx, group in enumerate(grouped_chunks):
            insert_chunk(
                conn=conn,
                document_id=document_id,
                chunk_index=idx,
                text=build_chunk_text(group),
                timestamp_start=group[0].timestamp,
                timestamp_end=group[-1].timestamp,
                embedding_id=None,
            )

        print(f"Imported conversation: {conv.title} | messages={len(conv.messages)} | chunks={len(grouped_chunks)}")
        imported += 1

    print()
    print(f"ChatGPT import finished. Imported={imported}, skipped={skipped}")


if __name__ == "__main__":
    main()