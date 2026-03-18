import csv
import sys
from pathlib import Path

from app.ingestion.common.db import (
    document_exists_by_raw_path,
    get_connection,
    insert_chunk,
    insert_document,
    insert_source,
)
from app.ingestion.teams.parser import parse_teams_thread_html


DISCOVERY_CSV = Path("data/processed/teams/discovery/teams_message_candidates.csv")
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


def should_skip_thread(path: str) -> bool:
    name = Path(path).name.lower()

    if name.startswith("card"):
        return True

    if name.startswith("polls"):
        return True

    return False


def load_existing_thread_paths(limit: int | None = None) -> list[str]:
    rows = []
    with DISCOVERY_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        seen = set()

        for row in reader:
            if row.get("thread_html_exists") != "True":
                continue

            path = (row.get("thread_html_path") or "").strip()
            if not path:
                continue

            if should_skip_thread(path):
                continue

            if path in seen:
                continue

            seen.add(path)
            rows.append(path)

            if limit and len(rows) >= limit:
                break

    return rows


def import_one_thread(file_path: str) -> bool:
    if document_exists_by_raw_path(file_path):
        print(f"Skipping already imported thread: {file_path}")
        return False

    parsed = parse_teams_thread_html(file_path)

    if not parsed.messages:
        print(f"No messages extracted from thread: {file_path}")
        return False

    conn = get_connection()

    source_id = insert_source(
        conn=conn,
        source_type="teams",
        source_name="export_20260310",
    )

    document_id = insert_document(
        conn=conn,
        source_id=source_id,
        title=parsed.title,
        created_at=parsed.created_at,
        author="multiple",
        participants=parsed.participants,
        raw_path=parsed.raw_path,
    )

    grouped_chunks = chunk_messages(parsed.messages)

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

    print(f"Imported Teams thread: {file_path}")
    print(f"Participants: {parsed.participants}")
    print(f"Messages: {len(parsed.messages)}")
    print(f"Chunks: {len(grouped_chunks)}")
    return True


def main() -> None:
    # 1) explicit single file import
    if len(sys.argv) == 2:
        import_one_thread(sys.argv[1])
        return

    # 2) optional limit via CLI: python -m ... --limit 100
    limit = None
    if len(sys.argv) == 3 and sys.argv[1] == "--limit":
        limit = int(sys.argv[2])

    paths = load_existing_thread_paths(limit=limit)

    print(f"Discovered Teams thread HTML files to process: {len(paths)}")

    imported = 0
    skipped = 0
    failed = 0

    for idx, path in enumerate(paths, start=1):
        print()
        print(f"[{idx}/{len(paths)}] Processing: {path}")

        try:
            did_import = import_one_thread(path)
            if did_import:
                imported += 1
            else:
                skipped += 1
        except Exception as e:
            failed += 1
            print(f"FAILED: {path}")
            print(f"ERROR: {e}")

    print()
    print("Teams import finished.")
    print(f"Imported: {imported}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()