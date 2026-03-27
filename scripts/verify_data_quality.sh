#!/usr/bin/env bash
# verify_data_quality.sh — Periodic data quality check
# Run every 4 hours via cron
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[$(date '+%F %T')] Data quality verification starting..."

# 1. Check for unembedded chunks
PENDING=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -tAc \
    "SELECT count(*) FROM chunks WHERE embedding_id IS NULL OR embedding_status != 'done';")
PENDING=$(echo "$PENDING" | tr -d '[:space:]')

if [ "$PENDING" -gt 0 ]; then
    echo "  EMBEDDING: $PENDING chunks pending — running indexer"
    TIKTOKEN_CACHE_DIR=/tmp/tiktoken_cache .venv/bin/python -m app.retrieval.index_chunks --batch-size 100 --limit 500
else
    echo "  EMBEDDING: OK (0 pending)"
fi

# 2. Check entity coverage
TOTAL_CHUNKS=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -tAc "SELECT count(*) FROM chunks;")
ENTITY_CHUNKS=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -tAc "SELECT count(DISTINCT chunk_id) FROM chunk_entities;")
TOTAL_CHUNKS=$(echo "$TOTAL_CHUNKS" | tr -d '[:space:]')
ENTITY_CHUNKS=$(echo "$ENTITY_CHUNKS" | tr -d '[:space:]')
ENTITY_PCT=$((100 * ENTITY_CHUNKS / TOTAL_CHUNKS))
echo "  ENTITIES: ${ENTITY_CHUNKS}/${TOTAL_CHUNKS} chunks (${ENTITY_PCT}%)"

if [ "$ENTITY_PCT" -lt 20 ]; then
    echo "  ENTITIES: Below 20% — running extraction (100 chunks)"
    ANTHROPIC_EXTRACTION_MODEL=claude-haiku-4-5 .venv/bin/python -m app.extraction.entities --candidates-only 100 2>/dev/null &
fi

# 3. Check event coverage
EVENTS=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -tAc "SELECT count(*) FROM events;")
EVENTS=$(echo "$EVENTS" | tr -d '[:space:]')
echo "  EVENTS: $EVENTS total"

# 4. Check source freshness
echo "  FRESHNESS:"
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -tAc "
SELECT source_type || ': ' || COALESCE(MAX(created_at)::date::text, 'N/A') || ' (' || 
       COALESCE((CURRENT_DATE - MAX(created_at)::date)::text, '?') || ' days ago)'
FROM documents d JOIN sources s ON d.source_id = s.id
WHERE created_at IS NOT NULL
GROUP BY source_type ORDER BY MAX(created_at) DESC;" | while read line; do
    echo "    $line"
done

# 5. Check for orphan/corrupt data
ORPHAN=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -tAc \
    "SELECT count(*) FROM chunks WHERE document_id NOT IN (SELECT id FROM documents);")
ORPHAN=$(echo "$ORPHAN" | tr -d '[:space:]')
if [ "$ORPHAN" -gt 0 ]; then
    echo "  WARNING: $ORPHAN orphan chunks found!"
else
    echo "  INTEGRITY: OK (0 orphans)"
fi

# 6. Check services
API_STATUS=$(curl -sf http://127.0.0.1:8000/health 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "DOWN")
QDRANT_STATUS=$(curl -sf http://127.0.0.1:6333/collections 2>/dev/null && echo "OK" || echo "DOWN")
echo "  SERVICES: API=${API_STATUS}, Qdrant=${QDRANT_STATUS}"

echo "[$(date '+%F %T')] Verification complete."
