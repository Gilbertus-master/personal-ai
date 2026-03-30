#!/usr/bin/env bash
set -euo pipefail

LOCKFILE=/tmp/weekly_synthesis.lock
exec 9>"$LOCKFILE"
flock -n 9 || { echo "[$(date)] weekly_synthesis already running, exiting."; exit 0; }
trap 'rm -f "$LOCKFILE"' EXIT INT TERM

cd /home/sebastian/personal-ai
source .venv/bin/activate || { echo "[$(date)] ERROR: venv activation failed"; exit 1; }

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Generating weekly synthesis..."
python -m app.retrieval.weekly_synthesis "$@"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done."
