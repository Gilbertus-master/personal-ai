import sys
from pathlib import Path

import structlog

from app.ingestion.common.db import (
    document_exists_by_raw_path,
    insert_chunks_batch,
    insert_document,
    insert_source,
)
from app.ingestion.whatsapp.parser import parse_whatsapp_file, extract_participants, WhatsAppMessage

log = structlog.get_logger(__name__)

CHUNK_TARGET_CHARS = 5000


def _format_line(msg: WhatsAppMessage) -> str:
    return f"[{msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author}: {msg.text}"


def build_chunk_text(messages) -> str:
    return "\n".join(_format_line(msg) for msg in messages)


def chunk_messages(messages: list[WhatsAppMessage]) -> list[list[WhatsAppMessage]]:
    chunks = []
    current = []
    current_len = 0

    for msg in messages:
        line = _format_line(msg)
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
        print("Usage: python -m app.ingestion.whatsapp.importer <path_to_chat.txt>")
        sys.exit(1)

    file_path = Path(sys.argv[1]).resolve()
    source_name = file_path.stem

    if document_exists_by_raw_path(str(file_path)):
        print(f"Skipping already imported file: {file_path}")
        sys.exit(0)

    try:
        messages = parse_whatsapp_file(file_path)
    except (FileNotFoundError, UnicodeDecodeError) as exc:
        log.error("whatsapp_parse_failed", path=str(file_path), error=str(exc))
        sys.exit(1)
    participants = extract_participants(messages)

    if not messages:
        print("No messages parsed.")
        sys.exit(1)

    source_id = insert_source(
        source_type="whatsapp",
        source_name=source_name,
    )

    document_id = insert_document(
        source_id=source_id,
        title=source_name,
        created_at=messages[0].timestamp,
        author="multiple",
        participants=participants,
        raw_path=str(file_path),
    )

    grouped_chunks = chunk_messages(messages)

    insert_chunks_batch([
        {
            "document_id": document_id,
            "chunk_index": idx,
            "text": build_chunk_text(group),
            "timestamp_start": group[0].timestamp,
            "timestamp_end": group[-1].timestamp,
            "embedding_id": None,
        }
        for idx, group in enumerate(grouped_chunks)
    ])

    print(f"Imported WhatsApp chat: {file_path}")
    print(f"Participants: {participants}")
    print(f"Messages: {len(messages)}")
    print(f"Chunks: {len(grouped_chunks)}")


if __name__ == "__main__":
    main()