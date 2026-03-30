import sys
from pathlib import Path

import structlog

from app.ingestion.common.db import (
    document_exists_by_raw_path,
    insert_chunk,
    insert_document,
    insert_source,
)
from app.ingestion.chatgpt.parser import ChatGPTMessage, parse_chatgpt_export_file

log = structlog.get_logger()

CHUNK_TARGET_CHARS = 5000


def build_chunk_text(messages) -> str:
    parts = []
    for msg in messages:
        ts = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S") if msg.timestamp else "unknown"
        parts.append(f"[{ts}] {msg.author}: {msg.text}")
    return "\n".join(parts)


def chunk_messages(messages: list[ChatGPTMessage]) -> list[list[ChatGPTMessage]]:
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
        log.error("chatgpt.import.usage", msg="Usage: python -m app.ingestion.chatgpt.importer <path_to_conversations_file.json>")
        sys.exit(1)

    file_path = Path(sys.argv[1])

    conversations = parse_chatgpt_export_file(file_path)

    if not conversations:
        log.warning("chatgpt.import.empty", file=str(file_path))
        sys.exit(1)

    imported = 0
    skipped = 0

    for conv in conversations:
        raw_path = f"{file_path}::{conv.conversation_id}"

        if document_exists_by_raw_path(raw_path):
            log.info("chatgpt.import.skip", title=conv.title)
            skipped += 1
            continue

        source_id = insert_source(
            source_type="chatgpt",
            source_name=file_path.name,
        )

        document_id = insert_document(
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
                document_id=document_id,
                chunk_index=idx,
                text=build_chunk_text(group),
                timestamp_start=group[0].timestamp,
                timestamp_end=group[-1].timestamp,
                embedding_id=None,
            )

        log.info("chatgpt.import.conversation", title=conv.title, messages=len(conv.messages), chunks=len(grouped_chunks))
        imported += 1

    log.info("chatgpt.import.finished", imported=imported, skipped=skipped)


if __name__ == "__main__":
    main()