#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Tracking responses..."
python -m app.analysis.response_tracker
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done."
