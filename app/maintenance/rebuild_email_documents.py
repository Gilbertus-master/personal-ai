from __future__ import annotations

import sys
from pathlib import Path

from app.ingestion.common.db import (
    delete_chunks_for_document,
    get_chunk_stats_for_document,
    get_document_row,
    insert_chunk,
    update_document_metadata,
)
from app.db.postgres import get_pg_connection
from app.ingestion.email.importer import build_participants, chunk_text
from app.ingestion.email.parser import build_email_text, parse_eml_file


def parse_raw_path(raw_path: str) -> tuple[Path, str, Path]:
    parts = raw_path.split("::")
    if len(parts) != 3:
        raise RuntimeError(f"Unexpected raw_path format: {raw_path}")

    pst_file = Path(parts[0])
    folder_path = parts[1]
    relative_eml_path = Path(parts[2])
    return pst_file, folder_path, relative_eml_path


def get_extracted_root_for_pst(pst_file: Path) -> Path:
    pst_stem = pst_file.stem
    return Path("/home/sebastian/personal-ai/data/processed/email_extracted") / pst_stem


def cleanup_candidate_status(document_id: int, status: str) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE email_cleanup_candidates SET cleanup_status = %s WHERE document_id = %s",
                (status, document_id),
            )
        conn.commit()


def rebuild_document(document_id: int) -> None:
    row = get_document_row(document_id)
    if row is None:
        raise RuntimeError(f"Document not found: {document_id}")

    raw_path = row["raw_path"]
    pst_file, _folder_path, relative_eml_path = parse_raw_path(raw_path)
    extracted_root = get_extracted_root_for_pst(pst_file)
    eml_path = extracted_root / relative_eml_path

    if not pst_file.exists():
        raise RuntimeError(f"PST file does not exist: {pst_file}")

    if not extracted_root.exists():
        raise RuntimeError(f"Extracted root does not exist: {extracted_root}")

    if not eml_path.exists():
        raise RuntimeError(f"EML file does not exist: {eml_path}")

    before = get_chunk_stats_for_document(document_id)

    parsed = parse_eml_file(eml_path, pst_file, extracted_root)
    full_text = build_email_text(parsed)
    chunks = chunk_text(full_text)

    delete_chunks_for_document(document_id)

    update_document_metadata(
        document_id=document_id,
        title=parsed.subject or "(no subject)",
        created_at=parsed.sent_at,
        author=parsed.from_addr or "unknown",
        participants=build_participants(parsed),
    )

    for chunk_index, chunk in enumerate(chunks):
        insert_chunk(
            conn=None,
            document_id=document_id,
            chunk_index=chunk_index,
            text=chunk,
            timestamp_start=parsed.sent_at,
            timestamp_end=parsed.sent_at,
            embedding_id=None,
        )

    after = get_chunk_stats_for_document(document_id)

    cleanup_candidate_status(document_id, "cleaned")

    print("=" * 80)
    print(f"Rebuilt document_id={document_id}")
    print(f"PST: {pst_file}")
    print(f"EML: {eml_path}")
    print(f"Before: chunk_count={before['chunk_count']} total_chars={before['total_chars']}")
    print(f"After:  chunk_count={after['chunk_count']} total_chars={after['total_chars']}")
    print("=" * 80)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.maintenance.rebuild_email_documents <document_id> [<document_id> ...]")
        sys.exit(1)

    document_ids: list[int] = []
    for value in sys.argv[1:]:
        try:
            document_ids.append(int(value))
        except ValueError:
            raise RuntimeError(f"Invalid document_id: {value}")

    for document_id in document_ids:
        rebuild_document(document_id)


if __name__ == "__main__":
    main()
