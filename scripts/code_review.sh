#!/usr/bin/env bash
# code_review.sh — Automated code review, one Claude session per file.
# Cron: */30 * * * * (every 30 min, 5 files per run)
#
# Usage: bash scripts/code_review.sh [batch_size]
#   Default: 5 files per run
set -euo pipefail
cd "$(dirname "$0")/.."

# Prevent concurrent runs
LOCKFILE="/tmp/code_review.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0) ))
    if [ "$LOCK_AGE" -gt 2700 ]; then
        echo "[$(date '+%H:%M:%S')] WARNING: Lock stale (${LOCK_AGE}s old). Breaking lock."
        flock -n 9 || { echo "[$(date '+%H:%M:%S')] Still locked. Exiting."; exit 0; }
    else
        echo "[$(date '+%H:%M:%S')] Skipping: code_review already running (lock age: ${LOCK_AGE}s)"
        exit 0
    fi
fi
touch "$LOCKFILE"

BATCH=${1:-5}

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Code review starting: batch=${BATCH}"

.venv/bin/python -m app.analysis.code_reviewer --batch "$BATCH"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Code review finished"
