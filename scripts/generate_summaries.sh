#!/usr/bin/env bash
# generate_summaries.sh — Generate daily or weekly summaries.
# Usage:
#   ./scripts/generate_summaries.sh daily 2026-03-22
#   ./scripts/generate_summaries.sh weekly 2026-03-17
#   ./scripts/generate_summaries.sh daily-range 2026-03-01 2026-03-23
set -euo pipefail

cd "$(dirname "$0")/.."

MODE="${1:-daily}"
DATE="${2:-}"
DATE_TO="${3:-}"

if [ -z "$DATE" ]; then
    echo "Usage: $0 <daily|weekly|daily-range> <date> [date_to]"
    exit 1
fi

export TIKTOKEN_CACHE_DIR=/tmp/tiktoken_cache

if [ "$MODE" = "daily-range" ]; then
    if [ -z "$DATE_TO" ]; then
        echo "daily-range requires date_to: $0 daily-range 2026-03-01 2026-03-23"
        exit 1
    fi
    echo "==> Generating daily summaries from $DATE to $DATE_TO"
    CURRENT="$DATE"
    while [[ "$CURRENT" < "$DATE_TO" ]]; do
        echo "==> Processing: $CURRENT"
        .venv/bin/python -c "
import json
from app.retrieval.summaries import generate_daily_summaries
results = generate_daily_summaries('$CURRENT')
for r in results:
    status = r.get('status', '?')
    area = r.get('area', '?')
    chunks = r.get('chunks_used', 0)
    print(f'  {area}: {status} (chunks={chunks})')
"
        CURRENT=$(date -d "$CURRENT + 1 day" +%F)
    done
elif [ "$MODE" = "weekly" ]; then
    echo "==> Generating weekly summaries for week starting $DATE"
    .venv/bin/python -c "
import json
from app.retrieval.summaries import generate_weekly_summaries
results = generate_weekly_summaries('$DATE')
for r in results:
    status = r.get('status', '?')
    area = r.get('area', '?')
    chunks = r.get('chunks_used', 0)
    print(f'  {area}: {status} (chunks={chunks})')
"
else
    echo "==> Generating daily summaries for $DATE"
    .venv/bin/python -c "
import json
from app.retrieval.summaries import generate_daily_summaries
results = generate_daily_summaries('$DATE')
for r in results:
    status = r.get('status', '?')
    area = r.get('area', '?')
    chunks = r.get('chunks_used', 0)
    print(f'  {area}: {status} (chunks={chunks})')
"
fi

echo "==> Done"
