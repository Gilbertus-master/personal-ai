#!/usr/bin/env bash
# communication_effectiveness.sh — Weekly communication analysis.
# Standing order effectiveness, channel analysis, adaptive authority.
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date)] Running communication effectiveness analysis..."

echo "--- Standing Order Effectiveness ---"
python -c "
from app.analysis.standing_order_effectiveness import run_all_order_analysis
import json
print(json.dumps(run_all_order_analysis(), ensure_ascii=False, indent=2, default=str))
"

echo "--- Channel Effectiveness ---"
python -c "
from app.analysis.channel_effectiveness import run_channel_analysis
import json
print(json.dumps(run_channel_analysis(), ensure_ascii=False, indent=2, default=str))
"

echo "--- Adaptive Authority ---"
python -c "
from app.orchestrator.adaptive_authority import run_adaptive_authority
import json
print(json.dumps(run_adaptive_authority(), ensure_ascii=False, indent=2, default=str))
"

echo "[$(date)] Done."
