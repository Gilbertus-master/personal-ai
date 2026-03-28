#!/usr/bin/env bash
# plaud_sync.sh — Automatic Plaud Pin S audio sync.
# Runs every 15 min via cron. Silently skips if no token available.
set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate 2>/dev/null || true

# Load env for PLAUD_AUTH_TOKEN
if [ -f .env ]; then
    set -a; source .env 2>/dev/null || true; set +a
fi

echo "[$(date '+%F %T')] Plaud sync starting..."

# Run sync (50 latest recordings). Script handles dedup internally.
.venv/bin/python -m app.ingestion.plaud_sync 50 2>&1 || {
    echo "[$(date '+%F %T')] Plaud sync failed (exit $?) — token may be expired"
}

echo "[$(date '+%F %T')] Plaud sync done."
