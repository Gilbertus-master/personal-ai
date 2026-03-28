#!/usr/bin/env bash
set -euo pipefail

LOCKFILE=/tmp/calendar_check.lock
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] Already running. Exiting."
    exit 0
fi
trap 'flock -u 9; rm -f $LOCKFILE' EXIT INT TERM

cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true
echo "[$(date)] Running calendar check..."
python -m app.orchestrator.calendar_manager
echo "[$(date)] Done."
