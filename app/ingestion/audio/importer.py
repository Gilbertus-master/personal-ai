"""
Importer for Plaud Pin S audio transcriptions.

Usage:
    python -m app.ingestion.audio.importer <directory_with_transcripts>
    python -m app.ingestion.audio.importer <directory> --limit 100
    python -m app.ingestion.audio.importer <single_file.txt>
"""
from __future__ import annotations

import structlog
import sys
from pathlib import Path

from app.ingestion.common.db import (
    document_exists_by_raw_path,
    insert_chunk,
    insert_document,
    insert_source,
)
from app.ingestion.audio.parser import (
    ParsedTranscript,
    build_transcript_text,
    collect_transcript_files,
    parse_transcript_file,
)

log = structlog.get_logger(__name__)

CHUNK_TARGET_CHARS = 3000
CHUNK_OVERLAP_CHARS = 300


def chunk_text(text: str) -> list[str]:
    """Split transcript text into chunks for embedding."""
    text = (text or "").strip()
    if not text:
        return [""]

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + CHUNK_TARGET_CHARS, length)

        # Try to break at sentence/paragraph boundary
        if end < length:
            for sep in ["\n\n", "\n", ". ", "? ", "! "]:
                last_sep = text.rfind(sep, start + CHUNK_TARGET_CHARS // 2, end)
                if last_sep > start:
                    end = last_sep + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break

        start = max(end - CHUNK_OVERLAP_CHARS, start + 1)

    return chunks


def build_participants(parsed: ParsedTranscript) -> list[str]:
    return parsed.participants


def import_transcript(
    parsed: ParsedTranscript,
    source_id: int,
) -> tuple[int, int]:
    """Import a single parsed transcript into the database."""
    if document_exists_by_raw_path(parsed.raw_path):
        return 0, 0

    full_text = build_transcript_text(parsed)
    chunks = chunk_text(full_text)

    document_id = insert_document(
        conn=None,
        source_id=source_id,
        title=parsed.title,
        created_at=parsed.recorded_at,
        author=parsed.participants[0] if parsed.participants else None,
        participants=build_participants(parsed),
        raw_path=parsed.raw_path,
    )

    for chunk_index, chunk in enumerate(chunks):
        insert_chunk(
            conn=None,
            document_id=document_id,
            chunk_index=chunk_index,
            text=chunk,
            timestamp_start=parsed.recorded_at,
            timestamp_end=parsed.recorded_at,
            embedding_id=None,
        )

    return 1, len(chunks)


def import_transcripts(
    path: Path,
    source_name: str = "plaud_pin_s",
    limit: int | None = None,
) -> tuple[int, int, int]:
    """Import transcript files from a directory or single file."""
    source_type = "audio_transcript"

    log.info(f"Creating source: type={source_type}, name={source_name}")
    source_id = insert_source(conn=None, source_type=source_type, source_name=source_name)

    if path.is_file():
        files = [path]
    else:
        files = collect_transcript_files(path)

    if not files:
        log.info(f"No transcript files found in {path}")
        return 0, 0, 0

    if limit:
        files = files[:limit]
        log.info(f"LIMIT: processing first {len(files)} files")

    total_docs = 0
    total_chunks = 0
    skipped = 0
    errors = 0

    for idx, file_path in enumerate(files, start=1):
        if idx % 10 == 0:
            log.info(f"Processing [{idx}/{len(files)}]: {file_path.name}")

        try:
            parsed = parse_transcript_file(file_path)
        except Exception as e:
            errors += 1
            log.info(f"ERROR parsing {file_path}: {e}")
            continue

        docs, chunks = import_transcript(parsed, source_id)
        if docs == 0:
            skipped += 1
        else:
            total_docs += docs
            total_chunks += chunks

    print(
        f"Done: {len(files)} files processed, "
        f"{total_docs} imported, {skipped} skipped (duplicates), "
        f"{errors} errors, {total_chunks} chunks created"
    )
    return total_docs, total_chunks, skipped


def main() -> None:
    if len(sys.argv) < 2:
        log.info("Usage: python -m app.ingestion.audio.importer <path> [--limit N]")
        sys.exit(1)

    path = Path(sys.argv[1]).resolve()
    if not path.exists():
        log.info(f"Path does not exist: {path}")
        sys.exit(1)

    limit = None
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        limit = int(sys.argv[idx + 1])

    source_name = "plaud_pin_s"
    if "--source-name" in sys.argv:
        idx = sys.argv.index("--source-name")
        source_name = sys.argv[idx + 1]

    import_transcripts(path, source_name=source_name, limit=limit)


if __name__ == "__main__":
    main()
