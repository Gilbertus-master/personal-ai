#!/usr/bin/env bash
# Feedback Calibration — runs evaluation trends, weak areas, and optimization report
# Usage: bash scripts/feedback_calibration.sh [days]
# Cron: 0 6 * * 1  (Monday 7:00 CET)

set -euo pipefail
cd /home/sebastian/personal-ai

DAYS="${1:-30}"

echo "=== Feedback Calibration (last ${DAYS} days) ==="
echo ""

echo "--- Evaluation Trends ---"
python -c "
import json
from app.analysis.feedback_persistence import get_evaluation_trends
result = get_evaluation_trends(days=${DAYS})
print(json.dumps(result, indent=2, default=str))
"

echo ""
echo "--- Weak Areas ---"
python -c "
import json
from app.analysis.feedback_persistence import get_weak_areas
result = get_weak_areas(days=${DAYS})
print(json.dumps(result, indent=2, default=str))
"

echo ""
echo "--- Optimization Report ---"
python -c "
import json
from app.analysis.threshold_optimizer import generate_optimization_report
result = generate_optimization_report(days=${DAYS})
print(json.dumps(result, indent=2, default=str))
"

echo ""
echo "=== Calibration complete ==="
