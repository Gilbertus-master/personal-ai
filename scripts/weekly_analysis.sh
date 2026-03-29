#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running weekly analysis..."

echo "--- Sentiment Scan ---"
python -c "
from app.analysis.sentiment_tracker import run_weekly_sentiment_scan
import json
print(json.dumps(run_weekly_sentiment_scan(), ensure_ascii=False, indent=2, default=str))
"

echo "--- Wellbeing Check ---"
python -c "
from app.analysis.wellbeing_monitor import run_wellbeing_check
import json
print(json.dumps(run_wellbeing_check(), ensure_ascii=False, indent=2, default=str))
"

echo "--- Predictive Scan ---"
python -c "
from app.analysis.predictive_alerts import run_predictive_scan
import json
print(json.dumps(run_predictive_scan(), ensure_ascii=False, indent=2, default=str))
"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Weekly analysis complete."
