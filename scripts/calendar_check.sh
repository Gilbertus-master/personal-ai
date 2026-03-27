#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true
echo "[$(date)] Running calendar check..."
python -m app.orchestrator.calendar_manager
echo "[$(date)] Done."
