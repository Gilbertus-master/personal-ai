#!/usr/bin/env bash
# Deep fixer — Tier 3: research + plan + orchestrator for stuck bugs
# Cron: 0 */2 * * * cd /home/sebastian/personal-ai && bash scripts/deep_fix.sh >> logs/deep_fix.log 2>&1
#
# Processes max 2 bugs per run, $2 budget each = max $4/run, $48/day
set -euo pipefail
cd "$(dirname "$0")/.."

# Prevent concurrent runs
LOCKFILE="/tmp/deep_fix.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    echo "[$(date '+%H:%M:%S')] Skipping: deep_fix already running"
    exit 0
fi
touch "$LOCKFILE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Deep fix starting..."

.venv/bin/python -m app.analysis.autofixer.tier3_deep_fixer

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Deep fix finished"
