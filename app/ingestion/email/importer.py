from __future__ import annotations

import sys
from pathlib import Path

from app.ingestion.common.db import (
    _run_sql_all_lines,
    get_connection,
    insert_chunk,
    insert_document,
    insert_source,
)

from app.ingestion.email.parser import (
    ParsedEmail,
    build_email_text,
    collect_eml_files,
    parse_eml_file,
)

CHUNK_TARGET_CHARS = 2500
CHUNK_OVERLAP_CHARS = 250


def dedupe_keep_order(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for v in values:
        v = v.strip()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def build_participants(parsed: ParsedEmail) -> list[str]:
    values: list[str] = []
    if parsed.from_addr:
        values.append(parsed.from_addr)
    values.extend(parsed.to_addrs)
    values.extend(parsed.cc_addrs)
    values.extend(parsed.bcc_addrs)
    return dedupe_keep_order(values)


def chunk_text(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return [""]

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + CHUNK_TARGET_CHARS, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break

        start = max(end - CHUNK_OVERLAP_CHARS, start + 1)

    return chunks


def sql_quote(value: str) -> str:
    return value.replace("'", "''")


def load_existing_raw_paths_for_source(source_type: str, source_name: str) -> set[str]:
    query = f"""
    SELECT d.raw_path
    FROM documents d
    JOIN sources s ON d.source_id = s.id
    WHERE s.source_type = '{sql_quote(source_type)}'
      AND s.source_name = '{sql_quote(source_name)}'
      AND d.raw_path IS NOT NULL;
    """

    try:
        lines = _run_sql_all_lines(query)
    except RuntimeError as e:
        message = str(e)
        if "no rows" in message.lower():
            return set()
        raise

    return set(lines)


def import_extracted_pst(
    pst_file: Path,
    extracted_root: Path,
    limit: int | None = None,
) -> tuple[int, int]:
    conn = get_connection()

    source_type = "email"
    source_name = pst_file.name

    print(f"Preparing source: type={source_type}, name={source_name}")
    source_id = insert_source(
        conn=conn,
        source_type=source_type,
        source_name=source_name,
    )

    print("Loading existing raw_path values for dedupe...")
    existing_raw_paths = load_existing_raw_paths_for_source(
        source_type=source_type,
        source_name=source_name,
    )
    print(f"Loaded {len(existing_raw_paths)} existing raw_path values")

    eml_files = collect_eml_files(extracted_root)
    if not eml_files:
        print(f"No EML files found in {extracted_root}")
        return 0, 0

    if limit is not None:
        eml_files = eml_files[:limit]
        print(f"LIMIT ENABLED: processing first {len(eml_files)} EML files")

    imported = 0
    skipped = 0
    errors = 0

    total = len(eml_files)
    print(f"Starting email import for {source_name}, files={total}")

    for idx, eml_path in enumerate(eml_files, start=1):
        try:
            parsed = parse_eml_file(eml_path, pst_file, extracted_root)
        except Exception as e:
            errors += 1
            print(f"ERROR parsing {eml_path}: {e}")
            continue

        if parsed.raw_path in existing_raw_paths:
            skipped += 1
            continue

        document_id = insert_document(
            conn=conn,
            source_id=source_id,
            title=parsed.subject or "(no subject)",
            created_at=parsed.sent_at,
            author=parsed.from_addr or "unknown",
            participants=build_participants(parsed),
            raw_path=parsed.raw_path,
        )

        full_text = build_email_text(parsed)
        chunks = chunk_text(full_text)

        for chunk_index, chunk in enumerate(chunks):
            insert_chunk(
                conn=conn,
                document_id=document_id,
                chunk_index=chunk_index,
                text=chunk,
                timestamp_start=parsed.sent_at,
                timestamp_end=parsed.sent_at,
                embedding_id=None,
            )

        existing_raw_paths.add(parsed.raw_path)
        imported += 1

        if idx % 100 == 0:
            print(
                f"Progress: {idx}/{total} processed | "
                f"imported={imported} skipped={skipped} errors={errors}"
            )

    print(
        f"Finished {source_name}: "
        f"processed={total}, imported={imported}, skipped={skipped}, errors={errors}"
    )
    return imported, skipped


def parse_limit_arg(value: str) -> int:
    try:
        limit = int(value)
    except ValueError:
        raise ValueError(f"Invalid limit value: {value}")

    if limit <= 0:
        raise ValueError(f"Limit must be > 0, got: {value}")

    return limit


def main() -> None:
    """
    Usage:
      python -m app.ingestion.email.importer <path_to_pst> <path_to_extracted_root>
      python -m app.ingestion.email.importer <path_to_pst> <path_to_extracted_root> --limit 1000
    """
    if len(sys.argv) not in {3, 5}:
        print(
            "Usage: python -m app.ingestion.email.importer "
            "<path_to_pst> <path_to_extracted_root> [--limit N]"
        )
        sys.exit(1)

    pst_file = Path(sys.argv[1]).resolve()
    extracted_root = Path(sys.argv[2]).resolve()

    if not pst_file.exists():
        print(f"PST file does not exist: {pst_file}")
        sys.exit(1)

    if not extracted_root.exists():
        print(f"Extracted root does not exist: {extracted_root}")
        sys.exit(1)

    limit = None
    if len(sys.argv) == 5:
        if sys.argv[3] != "--limit":
            print(f"Unknown argument: {sys.argv[3]}")
            sys.exit(1)
        try:
            limit = parse_limit_arg(sys.argv[4])
        except ValueError as e:
            print(str(e))
            sys.exit(1)

    import_extracted_pst(
        pst_file=pst_file,
        extracted_root=extracted_root,
        limit=limit,
    )


if __name__ == "__main__":
    main()
