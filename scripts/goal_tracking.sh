#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true
echo "[$(date)] Running goal tracking..."
python -m app.analysis.strategic_goals
echo "[$(date)] Done."
