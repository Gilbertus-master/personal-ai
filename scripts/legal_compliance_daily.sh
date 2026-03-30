#!/bin/bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Legal Compliance Daily Check"

.venv/bin/python -c "
from app.analysis.legal_compliance import run_daily_compliance_check
result = run_daily_compliance_check()
print(f'Daily check: {result}')
"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Done"
