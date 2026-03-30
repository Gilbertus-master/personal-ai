#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

LIMIT=${1:-500}
WORKERS=${2:-4}
MODEL=${3:-claude-haiku-4-5}

# Daily cost cap ($100/day)
DAILY_COST=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -tAc \
  "SELECT COALESCE(ROUND(SUM(cost_usd)::numeric, 2), 0) FROM api_costs WHERE module LIKE '%commitment%' AND created_at > NOW() - INTERVAL '24 hours'" 2>/dev/null || echo "0")
DAILY_COST=$(echo "$DAILY_COST" | tr -d '[:space:]')
if [ -n "$DAILY_COST" ] && [ "$(echo "$DAILY_COST > 100" | bc 2>/dev/null)" = "1" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] COST CAP: \$${DAILY_COST} exceeds \$100/day limit. Skipping."
    exit 0
fi

echo "[$(date)] Extracting commitments: limit=$LIMIT workers=$WORKERS model=$MODEL"
for i in $(seq 0 $((WORKERS - 1))); do
    python -m app.extraction.commitments --limit "$LIMIT" --worker "$i" --total "$WORKERS" --model "$MODEL" &
done
wait
echo "[$(date)] Commitment extraction complete."
