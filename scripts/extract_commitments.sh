#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

LIMIT=${1:-500}
WORKERS=${2:-4}
MODEL=${3:-claude-haiku-4-5}

echo "[$(date)] Extracting commitments: limit=$LIMIT workers=$WORKERS model=$MODEL"
for i in $(seq 0 $((WORKERS - 1))); do
    python -m app.extraction.commitments --limit "$LIMIT" --worker "$i" --total "$WORKERS" --model "$MODEL" &
done
wait
echo "[$(date)] Commitment extraction complete."
