import sys
from pathlib import Path

import structlog

from app.ingestion.common.db import (
    document_exists_by_raw_path,
    get_connection,
    insert_chunk,
    insert_document,
    insert_source,
)
from app.ingestion.docs.parser import parse_document_file

log = structlog.get_logger(__name__)


CHUNK_TARGET_CHARS = 5000
CHUNK_OVERLAP_CHARS = 600


def chunk_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + CHUNK_TARGET_CHARS, text_len)
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        start = max(end - CHUNK_OVERLAP_CHARS, start + 1)

    return chunks


def import_one_document(file_path: str | Path) -> bool:
    file_path = str(file_path)

    if document_exists_by_raw_path(file_path):
        log.info("document_already_imported", file_path=file_path)
        return False

    try:
        parsed = parse_document_file(file_path)
    except ValueError as exc:
        log.warning("unsupported_document_format", file_path=file_path, error=str(exc))
        return False

    if not parsed.text.strip():
        log.warning("no_text_extracted", file_path=file_path)
        return False

    conn = get_connection()

    source_id = insert_source(
        conn=conn,
        source_type="document",
        source_name=parsed.file_type,
    )

    document_id = insert_document(
        conn=conn,
        source_id=source_id,
        title=parsed.title,
        created_at=parsed.created_at,
        author=parsed.author,
        participants=parsed.participants,
        raw_path=parsed.raw_path,
    )

    chunks = chunk_text(parsed.text)

    skip_count = 0
    for idx, chunk in enumerate(chunks):
        result = insert_chunk(
            conn=conn,
            document_id=document_id,
            chunk_index=idx,
            text=chunk,
            timestamp_start=None,
            timestamp_end=None,
            embedding_id=None,
        )
        if result is None:
            skip_count += 1

    if skip_count > 0:
        log.warning(
            "duplicate_chunks_skipped",
            file_path=file_path,
            skip_count=skip_count,
            total_chunks=len(chunks),
        )

    log.info(
        "document_imported",
        file_path=file_path,
        file_type=parsed.file_type,
        title=parsed.title,
        chars=len(parsed.text),
        chunks=len(chunks),
        skipped=skip_count,
    )
    return True


def main() -> None:
    if len(sys.argv) < 2:
        log.error("usage_error", usage="python -m app.ingestion.docs.importer <path_to_document>")
        sys.exit(1)

    import_one_document(sys.argv[1])


if __name__ == "__main__":
    main()