#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date)] Running market intelligence scan..."

python -c "
from app.analysis.market_intelligence import run_market_scan
import json
print(json.dumps(run_market_scan(), ensure_ascii=False, indent=2, default=str))
"

echo "[$(date)] Done."
