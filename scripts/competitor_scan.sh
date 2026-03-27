#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date)] Running competitor intelligence scan..."

python -c "
from app.analysis.competitor_intelligence import run_competitor_scan
import json
print(json.dumps(run_competitor_scan(), ensure_ascii=False, indent=2, default=str))
"

echo "[$(date)] Done."
