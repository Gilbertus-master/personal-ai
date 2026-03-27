#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date)] Checking for upcoming meetings..."
python -c "
from app.analysis.meeting_prep import run_meeting_prep
import json
result = run_meeting_prep()
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
"
echo "[$(date)] Done."
