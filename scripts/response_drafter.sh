#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

MINUTES=${1:-30}
echo "[$(date)] Running response drafter (last ${MINUTES}min)..."
python -m app.orchestrator.response_drafter "$MINUTES"
echo "[$(date)] Done."
