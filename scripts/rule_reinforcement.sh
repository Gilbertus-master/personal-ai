#!/usr/bin/env bash
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true
echo "[$(date)] Running rule reinforcement..."
python -m app.analysis.rule_reinforcement
echo "[$(date)] Done."
