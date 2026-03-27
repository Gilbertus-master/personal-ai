#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date)] Running auto scenario scan..."

python -c "
from app.analysis.scenario_analyzer import run_auto_scenarios
import json
print(json.dumps(run_auto_scenarios(), ensure_ascii=False, indent=2, default=str))
"

echo "[$(date)] Done."
