#!/usr/bin/env bash
# Daily Performance Improvement Loop
# Cron: 0 2 * * * cd /home/sebastian/personal-ai && bash scripts/daily_perf_improvement.sh >> logs/perf_improvement.log 2>&1
set -euo pipefail

cd /home/sebastian/personal-ai
source .venv/bin/activate

echo "=== Perf Improvement Run: $(date -Iseconds) ==="

.venv/bin/python -m app.analysis.perf_improver.improvement_agent 2>&1

echo "=== Done: $(date -Iseconds) ==="
