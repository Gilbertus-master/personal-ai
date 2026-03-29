#!/usr/bin/env bash
# Strategic Radar — full pipeline: collect + patterns + recommendations + save
# Cron: 0 22 * * * cd /home/sebastian/personal-ai && bash scripts/strategic_radar.sh >> logs/strategic_radar.log 2>&1
set -euo pipefail
cd /home/sebastian/personal-ai
source .venv/bin/activate 2>/dev/null || true

echo "[$(date)] Running full strategic radar pipeline..."

python -c "
from app.analysis.strategic_radar import run_full_radar
import json
result = run_full_radar()
print(json.dumps({
    'snapshot_id': result.get('snapshot_id'),
    'patterns_count': len(result.get('patterns', [])),
    'recommendations_count': len(result.get('recommendations', [])),
    'latency_ms': result.get('latency_ms'),
}, ensure_ascii=False, indent=2, default=str))
"

echo "[$(date)] Strategic radar done."
