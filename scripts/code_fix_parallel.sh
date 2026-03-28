#!/usr/bin/env bash
# code_fix_parallel.sh — Parallel code fixer, N workers on different files.
# Cron: */10 8-21 * * * (every 10 min during 8:00-21:50 CET)
#
# Usage: bash scripts/code_fix_parallel.sh [workers]
#   Default: 3 workers
set -euo pipefail
cd "$(dirname "$0")/.."

# Prevent concurrent runs
LOCKFILE="/tmp/code_fix_parallel.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0) ))
    if [ "$LOCK_AGE" -gt 1800 ]; then
        echo "[$(date '+%H:%M:%S')] WARNING: Lock stale (${LOCK_AGE}s old). Breaking lock."
        flock -n 9 || { echo "[$(date '+%H:%M:%S')] Still locked. Exiting."; exit 0; }
    else
        echo "[$(date '+%H:%M:%S')] Skipping: code_fix_parallel already running (lock age: ${LOCK_AGE}s)"
        exit 0
    fi
fi
touch "$LOCKFILE"

WORKERS=${1:-3}

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Code fix parallel starting: workers=${WORKERS}"

.venv/bin/python -m app.analysis.code_fixer --parallel "$WORKERS"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Code fix parallel finished"
