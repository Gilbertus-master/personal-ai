#!/usr/bin/env bash
# turbo_extract.sh — Aggressive parallel entity+event extraction.
# Uses Haiku for speed + partitioned workers for zero duplication.
#
# Usage: bash scripts/turbo_extract.sh [batch_size] [num_workers] [model]
#   Default: 5000 chunks per worker, 12 workers per type, haiku model
set -euo pipefail
cd "$(dirname "$0")/.."

# Prevent concurrent runs — skip if workers already running
EXISTING=$(ps aux | grep -E "extraction\.(entities|events)" | grep -v grep | wc -l)
if [ "$EXISTING" -gt 0 ]; then
    echo "[$(date '+%H:%M:%S')] Skipping: $EXISTING workers already running"
    exit 0
fi

BATCH=${1:-5000}
WORKERS=${2:-12}
MODEL=${3:-claude-haiku-4-5-20251001}
LOG="logs/turbo_extract_$(date +%Y%m%d_%H%M).log"

echo "[$(date '+%H:%M:%S')] Turbo extract: batch=${BATCH}, workers=${WORKERS}, model=${MODEL}" | tee "$LOG"

# Report starting state
.venv/bin/python -c "
import psycopg, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg.connect(host=os.getenv('POSTGRES_HOST','127.0.0.1'),port=os.getenv('POSTGRES_PORT','5432'),dbname=os.getenv('POSTGRES_DB','gilbertus'),user=os.getenv('POSTGRES_USER','gilbertus'),password=os.getenv('POSTGRES_PASSWORD','gilbertus'))
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM entities'); ent = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM events'); ev = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM chunks c LEFT JOIN chunk_entities ce ON ce.chunk_id=c.id LEFT JOIN chunks_entity_checked cec ON cec.chunk_id=c.id WHERE ce.id IS NULL AND cec.chunk_id IS NULL')
need_ent = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM chunks c LEFT JOIN events e ON e.chunk_id=c.id LEFT JOIN chunks_event_checked cec ON cec.chunk_id=c.id WHERE e.id IS NULL AND cec.chunk_id IS NULL')
need_ev = cur.fetchone()[0]
print(f'Before: {ent} entities, {ev} events | Need: {need_ent} entity, {need_ev} event chunks')
conn.close()
" | tee -a "$LOG"

PIDS=()

# Launch entity workers with partitioning
for i in $(seq 0 $((WORKERS - 1))); do
    echo "[$(date '+%H:%M:%S')] Starting entity worker ${i}/${WORKERS} (${MODEL})..." | tee -a "$LOG"
    .venv/bin/python -m app.extraction.entities --model "${MODEL}" --worker "${i}/${WORKERS}" ${BATCH} >> "$LOG" 2>&1 &
    PIDS+=($!)
done

# Launch event workers with partitioning
for i in $(seq 0 $((WORKERS - 1))); do
    echo "[$(date '+%H:%M:%S')] Starting event worker ${i}/${WORKERS} (${MODEL})..." | tee -a "$LOG"
    .venv/bin/python -m app.extraction.events --model "${MODEL}" --worker "${i}/${WORKERS}" ${BATCH} >> "$LOG" 2>&1 &
    PIDS+=($!)
done

echo "[$(date '+%H:%M:%S')] All ${#PIDS[@]} workers launched: ${PIDS[*]}" | tee -a "$LOG"

# Wait for all
for pid in "${PIDS[@]}"; do
    wait "$pid" 2>/dev/null || true
done

echo "[$(date '+%H:%M:%S')] All workers finished" | tee -a "$LOG"

# Report final state
.venv/bin/python -c "
import psycopg, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg.connect(host=os.getenv('POSTGRES_HOST','127.0.0.1'),port=os.getenv('POSTGRES_PORT','5432'),dbname=os.getenv('POSTGRES_DB','gilbertus'),user=os.getenv('POSTGRES_USER','gilbertus'),password=os.getenv('POSTGRES_PASSWORD','gilbertus'))
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM entities'); ent = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM events'); ev = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM chunks c LEFT JOIN chunk_entities ce ON ce.chunk_id=c.id LEFT JOIN chunks_entity_checked cec ON cec.chunk_id=c.id WHERE ce.id IS NULL AND cec.chunk_id IS NULL')
need_ent = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM chunks c LEFT JOIN events e ON e.chunk_id=c.id LEFT JOIN chunks_event_checked cec ON cec.chunk_id=c.id WHERE e.id IS NULL AND cec.chunk_id IS NULL')
need_ev = cur.fetchone()[0]
print(f'After: {ent} entities, {ev} events | Remaining: {need_ent} entity, {need_ev} event chunks')
conn.close()
" | tee -a "$LOG"

echo "[$(date '+%H:%M:%S')] Done" | tee -a "$LOG"
