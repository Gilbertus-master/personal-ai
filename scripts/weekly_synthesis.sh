#!/usr/bin/env bash
set -euo pipefail

LOCKFILE=/tmp/weekly_synthesis.lock
exec 9>"$LOCKFILE"
flock -n 9 || { echo "[$(date)] weekly_synthesis already running, exiting."; exit 0; }
trap 'rm -f "$LOCKFILE"' EXIT INT TERM

cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Generating weekly synthesis..."
python -m app.retrieval.weekly_synthesis "$@"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done."
