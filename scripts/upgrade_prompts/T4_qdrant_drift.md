# TASK T4: Fix Qdrant Drift (3313 orphaned vectors)
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T4.done

## Context
- Qdrant collection `gilbertus_chunks` has 109,089 vectors
- PostgreSQL `chunks` table has 105,776 rows with embedding_id
- Difference: ~3,313 orphaned vectors in Qdrant with no matching chunk in PG
- These waste memory and slightly slow down every search
- Qdrant URL: http://localhost:6333, API key in .env as QDRANT_API_KEY
- Qdrant collection name: gilbertus_chunks (check QDRANT_COLLECTION in .env)

## What to do

Create and run a Python script at /home/sebastian/personal-ai/scripts/fix_qdrant_drift.py:

```python
#!/usr/bin/env python3
"""Remove orphaned vectors from Qdrant that have no corresponding chunk in PostgreSQL."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "gilbertus_chunks")
PG_DSN = f"host={os.getenv('POSTGRES_HOST','127.0.0.1')} port={os.getenv('POSTGRES_PORT','5432')} dbname={os.getenv('POSTGRES_DB','gilbertus')} user={os.getenv('POSTGRES_USER','gilbertus')} password={os.getenv('POSTGRES_PASSWORD','gilbertus')}"

import psycopg
from qdrant_client import QdrantClient

qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)

# Step 1: Get all embedding_ids from PostgreSQL
print("Fetching embedding_ids from PostgreSQL...")
with psycopg.connect(PG_DSN) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT embedding_id FROM chunks WHERE embedding_id IS NOT NULL")
        pg_ids = set(str(row[0]) for row in cur.fetchall())

print(f"PG has {len(pg_ids)} embedding_ids")

# Step 2: Scroll through all Qdrant points
print("Fetching all Qdrant point IDs (this may take a minute)...")
qdrant_ids = set()
offset = None
batch_size = 1000

while True:
    result = qdrant.scroll(
        collection_name=QDRANT_COLLECTION,
        limit=batch_size,
        offset=offset,
        with_payload=False,
        with_vectors=False,
    )
    points, next_offset = result
    for point in points:
        qdrant_ids.add(str(point.id))
    print(f"  fetched {len(qdrant_ids)} so far...", end='\r')
    if next_offset is None:
        break
    offset = next_offset

print(f"\nQdrant has {len(qdrant_ids)} total vectors")

# Step 3: Find orphans
orphan_ids = qdrant_ids - pg_ids
print(f"Orphaned vectors (in Qdrant but not in PG): {len(orphan_ids)}")

if not orphan_ids:
    print("No orphans found - nothing to clean up!")
    sys.exit(0)

if len(orphan_ids) > 10000:
    print(f"ERROR: Too many orphans ({len(orphan_ids)}), something is wrong. Aborting.")
    sys.exit(1)

# Step 4: Delete orphans in batches
print(f"Deleting {len(orphan_ids)} orphaned vectors...")
orphan_list = list(orphan_ids)
batch_size = 100
deleted = 0
for i in range(0, len(orphan_list), batch_size):
    batch = orphan_list[i:i+batch_size]
    qdrant.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=batch,
    )
    deleted += len(batch)
    print(f"  deleted {deleted}/{len(orphan_ids)}", end='\r')

print(f"\nDone! Deleted {deleted} orphaned vectors.")

# Step 5: Verify
from qdrant_client.http.models import CountRequest
final_count = qdrant.count(collection_name=QDRANT_COLLECTION)
print(f"Qdrant now has: {final_count.count} vectors")
print(f"PG has: {len(pg_ids)} chunks")
print(f"Drift: {final_count.count - len(pg_ids)} (should be ~0)")
```

Run it:
```
cd /home/sebastian/personal-ai && .venv/bin/python scripts/fix_qdrant_drift.py 2>&1 | tee /tmp/gilbertus_upgrade/logs/T4.log
```

## Completion
```
echo "done" > /tmp/gilbertus_upgrade/status/T4.done
openclaw system event --text "Upgrade T4 done: Qdrant drift fixed" --mode now
```
