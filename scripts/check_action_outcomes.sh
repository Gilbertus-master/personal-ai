#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true
echo "[$(date)] Checking action outcomes..."
python -m app.analysis.action_outcome_tracker
echo "[$(date)] Done."
