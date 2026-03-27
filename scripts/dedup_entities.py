#!/usr/bin/env python3
"""
Deduplicate entities by exact case-insensitive canonical_name match.

For each group of duplicates (same entity_type + lower(trim(canonical_name))):
1. Keep the lowest-ID entity as "keeper"
2. Migrate chunk_entities and event_entities to keeper
3. Delete duplicate entities
4. Add trigram index for ongoing fuzzy matching

Run: .venv/bin/python scripts/dedup_entities.py [--dry-run]
"""
import sys
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

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


def main():
    conn = get_conn()
    cur = conn.cursor()

    # Step 0: Counts
    cur.execute("SELECT COUNT(*) FROM entities")
    total_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM chunk_entities")
    ce_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM event_entities")
    ee_before = cur.fetchone()[0]
    print(f"=== BEFORE: {total_before} entities, {ce_before} chunk_entities, {ee_before} event_entities ===")

    if DRY_RUN:
        print("[DRY RUN]\n")

    # Step 1: Build dedup mapping
    print("Step 1: Finding exact case-insensitive duplicates...")
    cur.execute("""
        CREATE TEMP TABLE entity_dedup AS
        SELECT id, entity_type, canonical_name,
               FIRST_VALUE(id) OVER (
                   PARTITION BY entity_type, LOWER(TRIM(canonical_name))
                   ORDER BY id
               ) as keeper_id
        FROM entities
    """)
    cur.execute("SELECT COUNT(*) FROM entity_dedup WHERE id != keeper_id")
    to_delete = cur.fetchone()[0]
    print(f"  Duplicates to merge: {to_delete}")

    if to_delete == 0:
        print("No duplicates. Done.")
        conn.close()
        return

    # Step 2: Migrate chunk_entities
    print("Step 2: Migrating chunk_entities...")
    cur.execute("""
        INSERT INTO chunk_entities (chunk_id, entity_id, mention_text, confidence, created_at)
        SELECT ce.chunk_id, ed.keeper_id, ce.mention_text, ce.confidence, ce.created_at
        FROM chunk_entities ce
        JOIN entity_dedup ed ON ce.entity_id = ed.id
        WHERE ed.id != ed.keeper_id
        ON CONFLICT (chunk_id, entity_id, COALESCE(mention_text, '')) DO NOTHING
    """)
    ce_migrated = cur.rowcount
    print(f"  Migrated: {ce_migrated}")

    cur.execute("""
        DELETE FROM chunk_entities
        WHERE entity_id IN (SELECT id FROM entity_dedup WHERE id != keeper_id)
    """)
    ce_deleted = cur.rowcount
    print(f"  Old links removed: {ce_deleted}")

    # Step 3: Migrate event_entities
    print("Step 3: Migrating event_entities...")
    cur.execute("""
        INSERT INTO event_entities (event_id, entity_id, role, created_at)
        SELECT ee.event_id, ed.keeper_id, ee.role, ee.created_at
        FROM event_entities ee
        JOIN entity_dedup ed ON ee.entity_id = ed.id
        WHERE ed.id != ed.keeper_id
        ON CONFLICT (event_id, entity_id, COALESCE(role, '')) DO NOTHING
    """)
    ee_migrated = cur.rowcount
    print(f"  Migrated: {ee_migrated}")

    cur.execute("""
        DELETE FROM event_entities
        WHERE entity_id IN (SELECT id FROM entity_dedup WHERE id != keeper_id)
    """)
    ee_deleted = cur.rowcount
    print(f"  Old links removed: {ee_deleted}")

    # Step 4: Delete duplicate entities
    print("Step 4: Deleting duplicate entities...")
    cur.execute("""
        DELETE FROM entities
        WHERE id IN (SELECT id FROM entity_dedup WHERE id != keeper_id)
    """)
    entities_deleted = cur.rowcount
    print(f"  Deleted: {entities_deleted}")

    # Step 5: Cleanup
    cur.execute("DROP TABLE entity_dedup")

    # Step 6: Final counts
    cur.execute("SELECT COUNT(*) FROM entities")
    total_after = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM chunk_entities")
    ce_after = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM event_entities")
    ee_after = cur.fetchone()[0]

    print(f"\n=== AFTER: {total_after} entities ({total_before - total_after} removed) ===")
    print(f"  chunk_entities: {ce_after} (was {ce_before})")
    print(f"  event_entities: {ee_after} (was {ee_before})")

    if DRY_RUN:
        print("\n[DRY RUN] Rolling back.")
        conn.rollback()
    else:
        print("\n[COMMIT] Saving...")
        conn.commit()
        print("Done!")

    conn.close()


if __name__ == "__main__":
    main()
