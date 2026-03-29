#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Generating weekly synthesis..."
python -m app.retrieval.weekly_synthesis "$@"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done."
