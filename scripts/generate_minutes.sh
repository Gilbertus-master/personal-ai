#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date)] Generating meeting minutes..."
python -c "
from app.analysis.meeting_minutes import run_minutes_generation
import json
result = run_minutes_generation()
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
"
echo "[$(date)] Done."
