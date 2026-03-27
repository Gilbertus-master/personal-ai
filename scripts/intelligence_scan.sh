#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date)] Running intelligence scan..."

echo "--- Contract Check ---"
python -c "
from app.analysis.contract_tracker import run_contract_check
import json
print(json.dumps(run_contract_check(), ensure_ascii=False, indent=2, default=str))
"

echo "--- Delegation Report ---"
python -c "
from app.analysis.delegation_tracker import run_delegation_report
import json
print(json.dumps(run_delegation_report(), ensure_ascii=False, indent=2, default=str))
"

echo "--- Blind Spot Scan ---"
python -c "
from app.analysis.blind_spot_detector import run_blind_spot_scan
import json
print(json.dumps(run_blind_spot_scan(), ensure_ascii=False, indent=2, default=str))
"

echo "--- Network Analysis ---"
python -c "
from app.analysis.network_graph import run_network_analysis
import json
print(json.dumps(run_network_analysis(), ensure_ascii=False, indent=2, default=str))
"

echo "[$(date)] Intelligence scan complete."
