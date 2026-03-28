#!/usr/bin/env bash
# turbo_extract.sh — Aggressive parallel entity+event extraction.
# Uses Haiku for speed + partitioned workers for zero duplication.
#
# Usage: bash scripts/turbo_extract.sh [batch_size] [num_workers] [model]
#   Default: 5000 chunks per worker, 12 workers per type, haiku model
set -euo pipefail
cd "$(dirname "$0")/.."

# Prevent concurrent runs — use flock with 45-minute timeout.
# Old grep-based guard caused 36h+ blocks from zombie workers (lesson #13).
LOCKFILE="/tmp/turbo_extract.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    # Lock held — check if it's stale (older than 45 minutes)
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0) ))
    if [ "$LOCK_AGE" -gt 2700 ]; then
        echo "[$(date '+%H:%M:%S')] WARNING: Lock stale (${LOCK_AGE}s old). Breaking lock and killing orphan workers."
        pkill -f "app\.extraction\.(entities|events)" 2>/dev/null || true
        sleep 2
        flock -n 9 || { echo "[$(date '+%H:%M:%S')] Still locked after break attempt. Exiting."; exit 0; }
    else
        echo "[$(date '+%H:%M:%S')] Skipping: another turbo_extract running (lock age: ${LOCK_AGE}s)"
        exit 0
    fi
fi
# Touch lockfile so age tracking works
touch "$LOCKFILE"

cleanup() {
    echo "[$(date '+%H:%M:%S')] Cleaning up workers..." | tee -a "${LOG:-/dev/null}"
    for pid in "${PIDS[@]:-}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

BATCH=${1:-5000}
WORKERS=${2:-12}
MODEL=${3:-claude-haiku-4-5-20251001}
MAX_WORKER_TIME=1800  # 30 min max per worker
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

# Wait for all with timeout
START_WAIT=$(date +%s)
while true; do
    ALIVE=0
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            ALIVE=$((ALIVE + 1))
        fi
    done
    [ "$ALIVE" -eq 0 ] && break

    ELAPSED=$(( $(date +%s) - START_WAIT ))
    if [ "$ELAPSED" -gt "$MAX_WORKER_TIME" ]; then
        echo "[$(date '+%H:%M:%S')] TIMEOUT: $ALIVE workers still running after ${ELAPSED}s. Killing." | tee -a "$LOG"
        for pid in "${PIDS[@]}"; do
            kill "$pid" 2>/dev/null || true
        done
        sleep 2
        # Force kill survivors
        for pid in "${PIDS[@]}"; do
            kill -9 "$pid" 2>/dev/null || true
        done
        break
    fi
    sleep 5
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
