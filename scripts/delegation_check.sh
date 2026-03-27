#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true
echo "[$(date)] Checking delegations..."
python -m app.orchestrator.delegation_chain
echo "[$(date)] Done."
