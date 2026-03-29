#!/usr/bin/env bash
set -euo pipefail

LOCKFILE="/tmp/response_drafter.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0) ))
    if [ "$LOCK_AGE" -gt 1800 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: stale lock (${LOCK_AGE}s). Breaking."
        flock -n 9 || { echo "Still locked. Exiting."; exit 0; }
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Skipping: response_drafter already running"
        exit 0
    fi
fi
touch "$LOCKFILE"

cd /home/sebastian/personal-ai

MINUTES=${1:-30}
echo "[$(date)] Running response drafter (last ${MINUTES}min)..."
.venv/bin/python -m app.orchestrator.response_drafter "$MINUTES"
echo "[$(date)] Done."
