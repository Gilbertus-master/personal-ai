#!/usr/bin/env bash
# plaud_monitor.sh — Full Plaud automation pipeline.
# Runs as cron every 15 minutes.
#
# Pipeline: Plaud Pin S → (Bluetooth/app sync) → Plaud Cloud → auto-trigger
#           transcription → poll for completion → import to Gilbertus →
#           embed → extract entities/events.
#
# The ONLY manual step is syncing Plaud Pin S with the phone app.
# Everything else is fully automatic.
set -euo pipefail

LOCKFILE=/tmp/plaud_monitor.lock
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE") ))
  if [ "$LOCK_AGE" -lt 2700 ]; then echo "[$(date '+%Y-%m-%d %H:%M')] plaud_monitor already running (${LOCK_AGE}s), skipping"; exit 0; fi
  echo "[$(date '+%Y-%m-%d %H:%M')] plaud_monitor stale lock (${LOCK_AGE}s), stealing"
fi
trap 'rm -f "$LOCKFILE"' EXIT INT TERM

LOG=/home/sebastian/personal-ai/logs/plaud_monitor.log
exec >> "$LOG" 2>&1

cd "$(dirname "$0")/.."

timeout 2400 .venv/bin/python -m app.ingestion.plaud_monitor
