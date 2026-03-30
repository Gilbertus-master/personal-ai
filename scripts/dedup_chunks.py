#!/usr/bin/env python3
"""
Deduplicate chunks by text content (md5 hash).
For each group of duplicates, keeps the lowest-ID chunk and:
1. Migrates events, chunk_entities, event_checked, entity_checked to the keeper
2. Deletes the duplicate chunks (CASCADE handles documents FK if needed)
3. Adds text_hash column + unique index to prevent future duplicates

Run: .venv/bin/python scripts/dedup_chunks.py [--dry-run]
"""
import sys
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

DRY_RUN = "--dry-run" in sys.argv


def get_conn():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "gilbertus"),
        user=os.getenv("POSTGRES_USER", "gilbertus"),
        password=os.getenv("POSTGRES_PASSWORD", "gilbertus"),
    )


def main() -> None:
    conn = get_conn()
    cur = conn.cursor()

    # Step 0: Snapshot counts
    print("=== BEFORE ===")
    cur.execute("SELECT COUNT(*) FROM chunks")
    total_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT md5(text)) FROM chunks")
    unique_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM events")
    events_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM chunk_entities")
    ce_before = cur.fetchone()[0]
    print(f"  Chunks: {total_before} total, {unique_before} unique, {total_before - unique_before} duplicates")
    print(f"  Events: {events_before}, Chunk-entities: {ce_before}")

    if DRY_RUN:
        print("\n[DRY RUN] No changes will be made.")

    # Step 1: Find duplicate groups (keeper = lowest ID per hash)
    print("\n=== Step 1: Identify duplicate groups ===")
    cur.execute("""
        CREATE TEMP TABLE chunk_dedup AS
        SELECT id, md5(text) as hash,
               FIRST_VALUE(id) OVER (PARTITION BY md5(text) ORDER BY id) as keeper_id
        FROM chunks
    """)
    cur.execute("SELECT COUNT(*) FROM chunk_dedup WHERE id != keeper_id")
    dupes_count = cur.fetchone()[0]
    print(f"  Duplicates to process: {dupes_count}")

    if dupes_count == 0:
        print("No duplicates found. Exiting.")
        conn.close()
        return

    # Step 2: Migrate events from dupes to keepers
    print("\n=== Step 2: Migrate events ===")
    cur.execute("""
        UPDATE events SET chunk_id = cd.keeper_id
        FROM chunk_dedup cd
        WHERE events.chunk_id = cd.id AND cd.id != cd.keeper_id
    """)
    events_migrated = cur.rowcount
    print(f"  Events migrated: {events_migrated}")

    # Step 3: Migrate chunk_entities (handle conflicts with ON CONFLICT)
    print("\n=== Step 3: Migrate chunk_entities ===")
    # First, insert non-conflicting ones
    cur.execute("""
        INSERT INTO chunk_entities (chunk_id, entity_id, mention_text, confidence, created_at)
        SELECT cd.keeper_id, ce.entity_id, ce.mention_text, ce.confidence, ce.created_at
        FROM chunk_entities ce
        JOIN chunk_dedup cd ON ce.chunk_id = cd.id
        WHERE cd.id != cd.keeper_id
        ON CONFLICT (chunk_id, entity_id, COALESCE(mention_text, '')) DO NOTHING
    """)
    ce_migrated = cur.rowcount
    print(f"  Chunk-entities migrated: {ce_migrated}")

    # Delete the old chunk_entity links (they'll CASCADE anyway, but be explicit)
    cur.execute("""
        DELETE FROM chunk_entities
        WHERE chunk_id IN (SELECT id FROM chunk_dedup WHERE id != keeper_id)
    """)
    ce_deleted = cur.rowcount
    print(f"  Old chunk-entity links removed: {ce_deleted}")

    # Step 4: Migrate checked markers
    print("\n=== Step 4: Migrate checked markers ===")
    cur.execute("""
        INSERT INTO chunks_event_checked (chunk_id, checked_at)
        SELECT DISTINCT cd.keeper_id, cec.checked_at
        FROM chunks_event_checked cec
        JOIN chunk_dedup cd ON cec.chunk_id = cd.id
        WHERE cd.id != cd.keeper_id
        ON CONFLICT DO NOTHING
    """)
    print(f"  Event-checked migrated: {cur.rowcount}")

    cur.execute("""
        INSERT INTO chunks_entity_checked (chunk_id, checked_at)
        SELECT DISTINCT cd.keeper_id, cec.checked_at
        FROM chunks_entity_checked cec
        JOIN chunk_dedup cd ON cec.chunk_id = cd.id
        WHERE cd.id != cd.keeper_id
        ON CONFLICT DO NOTHING
    """)
    print(f"  Entity-checked migrated: {cur.rowcount}")

    # Clean old checked markers
    cur.execute("DELETE FROM chunks_event_checked WHERE chunk_id IN (SELECT id FROM chunk_dedup WHERE id != keeper_id)")
    cur.execute("DELETE FROM chunks_entity_checked WHERE chunk_id IN (SELECT id FROM chunk_dedup WHERE id != keeper_id)")

    # Step 5: Delete duplicate chunks
    print("\n=== Step 5: Delete duplicate chunks ===")
    cur.execute("""
        DELETE FROM chunks WHERE id IN (
            SELECT id FROM chunk_dedup WHERE id != keeper_id
        )
    """)
    chunks_deleted = cur.rowcount
    print(f"  Chunks deleted: {chunks_deleted}")

    # Step 6: Add text_hash column and unique index
    print("\n=== Step 6: Add text_hash column + unique index ===")
    cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS text_hash TEXT")
    cur.execute("UPDATE chunks SET text_hash = md5(text) WHERE text_hash IS NULL")
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_text_hash_doc
        ON chunks (document_id, text_hash)
    """)
    print("  text_hash column + unique index created")

    # Drop temp table
    cur.execute("DROP TABLE chunk_dedup")

    # Step 7: Final counts
    print("\n=== AFTER ===")
    cur.execute("SELECT COUNT(*) FROM chunks")
    total_after = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM events")
    events_after = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM chunk_entities")
    ce_after = cur.fetchone()[0]
    print(f"  Chunks: {total_after} (deleted {total_before - total_after})")
    print(f"  Events: {events_after} (lost {events_before - events_after})")
    print(f"  Chunk-entities: {ce_after}")

    if DRY_RUN:
        print("\n[DRY RUN] Rolling back all changes.")
        conn.rollback()
    else:
        print("\n[COMMIT] Saving changes...")
        conn.commit()
        print("Done!")

    conn.close()


if __name__ == "__main__":
    main()
