#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
LOCKFILE=/tmp/weekly_analysis.lock
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] weekly_analysis already running, exiting."
  exit 0
fi
trap 'rm -f $LOCKFILE' EXIT INT TERM

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running weekly analysis..."

echo "--- Sentiment Scan ---"
.venv/bin/python -c "
from app.analysis.sentiment_tracker import run_weekly_sentiment_scan
import json
print(json.dumps(run_weekly_sentiment_scan(), ensure_ascii=False, indent=2, default=str))
"

echo "--- Wellbeing Check ---"
.venv/bin/python -c "
from app.analysis.wellbeing_monitor import run_wellbeing_check
import json
print(json.dumps(run_wellbeing_check(), ensure_ascii=False, indent=2, default=str))
"

echo "--- Predictive Scan ---"
.venv/bin/python -c "
from app.analysis.predictive_alerts import run_predictive_scan
import json
print(json.dumps(run_predictive_scan(), ensure_ascii=False, indent=2, default=str))
"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Weekly analysis complete."
