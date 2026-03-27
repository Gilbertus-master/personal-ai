#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date)] Checking commitments..."
python -c "
from app.analysis.commitment_tracker import run_commitment_check
import json
result = run_commitment_check()
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
"
echo "[$(date)] Done."
