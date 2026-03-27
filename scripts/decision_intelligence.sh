#!/usr/bin/env bash
# decision_intelligence.sh — Decision Outcome Learning Loop.
# Auto-captures decisions, sends review reminders, analyzes patterns.
# Cron: 0 6 * * * (daily at 8:00 CET = 6:00 UTC)
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true
echo "[$(date)] Running decision intelligence..."
python -m app.analysis.decision_intelligence
echo "[$(date)] Done."
