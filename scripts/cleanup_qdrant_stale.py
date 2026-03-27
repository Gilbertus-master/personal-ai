#!/usr/bin/env python3
"""
Remove stale Qdrant vectors that point to deleted/nonexistent Postgres chunks.

After chunk dedup + Teams grouping, ~50k vectors reference chunks that no longer exist.
This script:
1. Scrolls all Qdrant point IDs
2. Compares against valid chunk IDs in Postgres
3. Deletes stale vectors in batches

Run: .venv/bin/python scripts/cleanup_qdrant_stale.py [--dry-run]
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointIdsList

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
sys.path.insert(0, str(BASE_DIR))

DRY_RUN = "--dry-run" in sys.argv

QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "gilbertus_chunks")

qdrant = QdrantClient(url=QDRANT_URL, timeout=60.0)


def get_valid_chunk_ids() -> set[int]:
    from app.db.postgres import get_pg_connection
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM chunks")
            return {row[0] for row in cur.fetchall()}


def scroll_all_qdrant_ids() -> list[int]:
    """Scroll through all points in Qdrant and collect their chunk_id payloads."""
    all_ids = []
    offset = None
    batch_size = 1000

    while True:
        results = qdrant.scroll(
            collection_name=COLLECTION,
            limit=batch_size,
            offset=offset,
            with_payload=["chunk_id"],
            with_vectors=False,
        )
        points, next_offset = results

        for point in points:
            chunk_id = point.payload.get("chunk_id") if point.payload else None
            if chunk_id is not None:
                all_ids.append((point.id, chunk_id))

        if next_offset is None or len(points) == 0:
            break
        offset = next_offset

    return all_ids


def main():
    print("=== Qdrant Stale Vector Cleanup ===")
    if DRY_RUN:
        print("[DRY RUN]\n")

    # Step 1: Valid chunk IDs
    print("Step 1: Loading valid chunk IDs from Postgres...")
    valid_ids = get_valid_chunk_ids()
    print(f"  Valid chunks: {len(valid_ids)}")

    # Step 2: All Qdrant points
    print("Step 2: Scrolling all Qdrant points...")
    qdrant_points = scroll_all_qdrant_ids()
    print(f"  Qdrant points: {len(qdrant_points)}")

    # Step 3: Find stale
    stale_point_ids = [pid for pid, cid in qdrant_points if cid not in valid_ids]
    print(f"  Stale vectors: {len(stale_point_ids)}")
    print(f"  Valid vectors: {len(qdrant_points) - len(stale_point_ids)}")

    if not stale_point_ids:
        print("\nNo stale vectors. Done.")
        return

    # Step 4: Delete in batches
    print(f"\nStep 3: Deleting {len(stale_point_ids)} stale vectors...")
    BATCH = 500
    deleted = 0
    for i in range(0, len(stale_point_ids), BATCH):
        batch = stale_point_ids[i:i + BATCH]
        if not DRY_RUN:
            qdrant.delete(
                collection_name=COLLECTION,
                points_selector=PointIdsList(points=batch),
            )
        deleted += len(batch)
        if deleted % 5000 == 0 or deleted == len(stale_point_ids):
            print(f"  Deleted: {deleted}/{len(stale_point_ids)}")

    # Step 5: Verify
    info = qdrant.get_collection(COLLECTION)
    print(f"\nAfter cleanup: {info.points_count} points in Qdrant")
    print(f"Expected: ~{len(valid_ids)} (valid chunks with embeddings)")
    print("Done!")


if __name__ == "__main__":
    main()
