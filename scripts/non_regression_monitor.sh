#!/bin/bash
# Non-regression continuous monitor — runs every 10 min
# Lightweight check: MCP, cron, tables, API health, Qdrant health
# Alerts via WhatsApp + DB insight on regression
#
# Cron: */10 * * * * cd /home/sebastian/personal-ai && bash scripts/non_regression_monitor.sh

set -euo pipefail
cd /home/sebastian/personal-ai

BASELINE_FILE="logs/.qc_baseline.json"
OPENCLAW="${HOME}/.npm-global/bin/openclaw"
WA_TARGET="+48505441635"
ERRORS=0
WARNINGS=""

# Skip if no baseline exists
if [ ! -f "$BASELINE_FILE" ]; then
    exit 0
fi

BASE_MCP=$(.venv/bin/python -c "import json; print(json.load(open('$BASELINE_FILE')).get('mcp',0))" 2>/dev/null || echo 0)
BASE_CRON=$(.venv/bin/python -c "import json; print(json.load(open('$BASELINE_FILE')).get('cron',0))" 2>/dev/null || echo 0)
BASE_TABLES=$(.venv/bin/python -c "import json; print(json.load(open('$BASELINE_FILE')).get('tables',0))" 2>/dev/null || echo 0)

# Check MCP tools
CURRENT_MCP=$(grep -c 'Tool(name=' mcp_gilbertus/server.py 2>/dev/null || echo 0)
if [ "$CURRENT_MCP" -lt "$BASE_MCP" ] 2>/dev/null; then
    WARNINGS="${WARNINGS}MCP: ${CURRENT_MCP} < baseline ${BASE_MCP}\n"
    ERRORS=$((ERRORS + 1))
fi

# Check DB tables
CURRENT_TABLES=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null || echo 0)
if [ "$CURRENT_TABLES" -lt "$BASE_TABLES" ] 2>/dev/null; then
    WARNINGS="${WARNINGS}Tables: ${CURRENT_TABLES} < baseline ${BASE_TABLES}\n"
    ERRORS=$((ERRORS + 1))
fi

# Check cron jobs
CURRENT_CRON=$(crontab -l 2>/dev/null | grep -v '^#' | grep -v '^$' | wc -l)
if [ "$CURRENT_CRON" -lt "$BASE_CRON" ] 2>/dev/null; then
    WARNINGS="${WARNINGS}Cron: ${CURRENT_CRON} < baseline ${BASE_CRON}\n"
    ERRORS=$((ERRORS + 1))
fi

# Check API health
API_STATUS=$(curl -sf --max-time 5 http://localhost:8000/health 2>/dev/null || echo "")
if [ -z "$API_STATUS" ]; then
    WARNINGS="${WARNINGS}Gilbertus API: not responding\n"
    ERRORS=$((ERRORS + 1))
fi

# Check Qdrant health
QDRANT_STATUS=$(curl -sf --max-time 5 http://localhost:6333/healthz 2>/dev/null || echo "")
if [ -z "$QDRANT_STATUS" ]; then
    WARNINGS="${WARNINGS}Qdrant: not responding\n"
    # Don't count as error — Qdrant may be restarting
fi

# Alert if regression detected
if [ $ERRORS -gt 0 ]; then
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M CET')
    ALERT_MSG="⚠️ ZASADA ZERO VIOLATION [$TIMESTAMP]\n${WARNINGS}Check: python3 scripts/non_regression_gate.py check"

    # Log to file
    echo -e "[${TIMESTAMP}] NON-REGRESSION ALERT:\n${WARNINGS}" >> logs/non_regression_alerts.log

    # Save insight to DB
    docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c \
        "INSERT INTO insights (insight_type, title, content, created_at)
         VALUES ('non_regression_alert',
                 'Zasada Zero: regresja wykryta',
                 '$(echo -e "$WARNINGS" | sed "s/'/\\''/g")',
                 NOW())" 2>/dev/null || true

    # WhatsApp alert (max 1 per hour to avoid spam)
    LAST_ALERT_FILE="logs/.last_nr_alert"
    SEND_ALERT=1
    if [ -f "$LAST_ALERT_FILE" ]; then
        LAST=$(cat "$LAST_ALERT_FILE")
        NOW=$(date +%s)
        DIFF=$((NOW - LAST))
        if [ $DIFF -lt 3600 ]; then
            SEND_ALERT=0  # Less than 1 hour since last alert
        fi
    fi

    if [ $SEND_ALERT -eq 1 ] && [ -f "$OPENCLAW" ] && [ -n "$WA_TARGET" ]; then
        $OPENCLAW message send --channel whatsapp --target "$WA_TARGET" \
            --message "$(echo -e "$ALERT_MSG")" 2>/dev/null || true
        date +%s > "$LAST_ALERT_FILE"
    fi
fi
