#!/usr/bin/env bash
# reindex_qdrant.sh — Re-indexes all chunks into Qdrant after data loss.
# This resets embedding_status so index_chunks.py picks them up again.
# WARNING: This calls OpenAI API for all chunks — may take hours and cost money.
set -euo pipefail

cd "$(dirname "$0")/.."

CONTAINER="gilbertus-postgres"
DB_USER="${POSTGRES_USER:-gilbertus}"
DB_NAME="${POSTGRES_DB:-gilbertus}"
BATCH_SIZE="${1:-100}"

echo "==> Qdrant re-indexing preparation"

# Count current state
TOTAL=$(docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM chunks WHERE embedding_id IS NOT NULL;")
TOTAL=$(echo "$TOTAL" | tr -d '[:space:]')
echo "==> Chunks with embedding_id: $TOTAL"

echo "==> Resetting embedding_status to 'pending' for all chunks..."
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c \
    "UPDATE chunks SET embedding_status = 'pending' WHERE embedding_status = 'done';"

echo "==> Starting re-indexing with batch_size=$BATCH_SIZE"
echo "==> This will call OpenAI API. Press Ctrl+C to stop at any time."
echo "==> Progress is saved per batch — you can resume by running this script again."

.venv/bin/python -m app.retrieval.index_chunks --batch-size "$BATCH_SIZE"

echo "==> Re-indexing complete"
