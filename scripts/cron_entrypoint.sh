#!/usr/bin/env bash
# Cron container entrypoint: generates crontab from registry and runs cron daemon
set -euo pipefail
cd /app

echo "[$(date)] Generating crontab from registry..."

# Generate crontab
python -c "
from app.orchestrator.cron_registry import generate_crontab
crontab = generate_crontab('sebastian')
print(crontab)
" > /etc/cron.d/gilbertus

chmod 0644 /etc/cron.d/gilbertus

# Export env vars for cron jobs
env | grep -E '^(ANTHROPIC|OPENAI|DATABASE|QDRANT|WHISPER|GILBERTUS|PLAUD|GRAPH|OPENCLAW|PATH)' > /app/.cronenv
echo "source /app/.cronenv" >> /etc/cron.d/gilbertus

echo "[$(date)] Crontab installed. Starting cron..."
cron -f
