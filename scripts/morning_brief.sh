#!/usr/bin/env bash
# morning_brief.sh — Generate the daily morning brief.
# Usage:
#   ./scripts/morning_brief.sh                     # today
#   ./scripts/morning_brief.sh --date 2026-03-20   # specific date
#   ./scripts/morning_brief.sh --force              # regenerate
#   ./scripts/morning_brief.sh --days 14            # custom lookback
#
# Cron (daily at 7:00):
#   0 7 * * * /home/sebastian/personal-ai/scripts/morning_brief.sh >> /home/sebastian/personal-ai/logs/morning_brief.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."

export TIKTOKEN_CACHE_DIR=/tmp/tiktoken_cache

echo "=== Morning Brief — $(date '+%Y-%m-%d %H:%M:%S') ==="

.venv/bin/python -m app.retrieval.morning_brief "$@"

echo "=== Done — $(date '+%Y-%m-%d %H:%M:%S') ==="
