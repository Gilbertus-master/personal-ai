#!/usr/bin/env bash
# Cron Health Check — run from crontab
# Usage: */10 * * * * cd /home/sebastian/personal-ai && bash scripts/cron_health_check.sh >> logs/cron_health.log 2>&1

set -euo pipefail

cd /home/sebastian/personal-ai

echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Starting cron health check..."

# Run health checker
.venv/bin/python -c "
from app.guardian.cron_health_checker import check_cron_health, check_cron_freshness
import json

health = check_cron_health()
freshness = check_cron_freshness()

print(f'Health: healthy={health[\"healthy\"]}, errors={health[\"errors_found\"]}')
print(f'Freshness: healthy={freshness[\"healthy\"]}, stale={freshness[\"stale_count\"]}')

if not health['healthy'] or not freshness['healthy']:
    print('WARNING: Issues detected!')
    if health.get('details'):
        for d in health['details'][:3]:
            print(f'  Log errors: {d[\"file\"]} ({d[\"error_count\"]} errors)')
    if freshness.get('details'):
        for d in freshness['details'][:3]:
            print(f'  Stale: {d[\"file\"]} ({d.get(\"age_human\", \"missing\")})')
"

echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Cron health check done."
