#!/usr/bin/env bash
# code_fix.sh — Automated code fixer, one finding per run.
# Cron: */15 8-21 * * * (every 15 min during 8:00-21:45 CET)
#
# Usage: bash scripts/code_fix.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# Prevent concurrent runs
LOCKFILE="/tmp/code_fix.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0) ))
    if [ "$LOCK_AGE" -gt 600 ]; then
        echo "[$(date '+%H:%M:%S')] WARNING: Lock stale (${LOCK_AGE}s old). Breaking lock."
        flock -n 9 || { echo "[$(date '+%H:%M:%S')] Still locked. Exiting."; exit 0; }
    else
        echo "[$(date '+%H:%M:%S')] Skipping: code_fix already running (lock age: ${LOCK_AGE}s)"
        exit 0
    fi
fi
touch "$LOCKFILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Code fix starting"

.venv/bin/python -m app.analysis.code_fixer

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Code fix finished"
