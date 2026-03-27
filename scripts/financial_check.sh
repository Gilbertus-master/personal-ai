#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true
echo "[$(date)] Running financial check..."
python -m app.analysis.financial_framework
echo "[$(date)] Done."
