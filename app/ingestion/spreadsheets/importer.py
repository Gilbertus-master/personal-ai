import sys
from pathlib import Path

from app.ingestion.common.db import (
    document_exists_by_raw_path,
    insert_chunk,
    insert_document,
    insert_source,
)
from app.ingestion.spreadsheets.parser import parse_spreadsheet_file


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


def import_one_spreadsheet(file_path: str | Path) -> bool:
    file_path = str(file_path)

    if document_exists_by_raw_path(file_path):
        print(f"Skipping already imported spreadsheet: {file_path}")
        return False

    parsed = parse_spreadsheet_file(file_path)

    if not parsed.text.strip():
        print(f"No text extracted from spreadsheet: {file_path}")
        return False

    source_id = insert_source(
        source_type="spreadsheet",
        source_name=parsed.file_type,
    )

    document_id = insert_document(
        source_id=source_id,
        title=parsed.title,
        created_at=parsed.created_at,
        author=parsed.author,
        participants=parsed.participants,
        raw_path=parsed.raw_path,
    )

    chunks = chunk_text(parsed.text)

    # Use document created_at as chunk timestamp (critical for event extraction)
    doc_timestamp = parsed.created_at

    for idx, chunk in enumerate(chunks):
        insert_chunk(
            document_id=document_id,
            chunk_index=idx,
            text=chunk,
            timestamp_start=doc_timestamp,
            timestamp_end=doc_timestamp,
            embedding_id=None,
        )

    print(f"Imported spreadsheet: {file_path}")
    print(f"Type: {parsed.file_type}")
    print(f"Title: {parsed.title}")
    print(f"Chars: {len(parsed.text)}")
    print(f"Chunks: {len(chunks)}")
    return True


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.ingestion.spreadsheets.importer <path_to_spreadsheet>")
        sys.exit(1)

    import_one_spreadsheet(sys.argv[1])


if __name__ == "__main__":
    main()