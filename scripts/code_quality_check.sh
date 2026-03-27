#!/usr/bin/env bash
# Code Quality Agent — daily automated check.
# Cron: 0 6 * * * cd /home/sebastian/personal-ai && bash scripts/code_quality_check.sh
# Also run manually after changes: bash scripts/code_quality_check.sh
set -uo pipefail
cd "$(dirname "$0")/.."

NOW=$(TZ=Europe/Warsaw date '+%Y-%m-%d %H:%M %Z')
ERRORS=0
WARNINGS=0
REPORT=""

add_error() { ERRORS=$((ERRORS + 1)); REPORT="${REPORT}\n[ERROR] $1"; }
add_warning() { WARNINGS=$((WARNINGS + 1)); REPORT="${REPORT}\n[WARN] $1"; }
add_ok() { REPORT="${REPORT}\n[OK] $1"; }

echo "=== Code Quality Check: ${NOW} ==="

# 1. Ruff lint
echo "1. Ruff lint..."
RUFF_OUTPUT=$(.venv/bin/ruff check app/ 2>/dev/null || true)
RUFF_ERRORS=$(echo "$RUFF_OUTPUT" | grep "^Found" | head -1 | grep -oP '^\d+' || echo "0")
if [ "$RUFF_ERRORS" -gt 50 ] 2>/dev/null; then
    add_error "Ruff: ${RUFF_ERRORS} lint errors (threshold: 50)"
elif [ "$RUFF_ERRORS" -gt 0 ] 2>/dev/null; then
    add_warning "Ruff: ${RUFF_ERRORS} lint errors (minor)"
else
    add_ok "Ruff: clean"
fi

# 2. Raw psycopg.connect (should use pool)
echo "2. Raw psycopg.connect..."
RAW_CONNECTS=$(grep -rn 'psycopg\.connect(' app/ --include="*.py" | grep -v 'psycopg_pool\|# pool\|test_' | wc -l)
if [ "$RAW_CONNECTS" -gt 0 ]; then
    add_error "Raw psycopg.connect found in ${RAW_CONNECTS} locations (use get_pg_connection from app/db/postgres.py)"
else
    add_ok "All DB connections use pool"
fi

# 3. print() in app/ production code
echo "3. print() in production..."
PRINTS=$(grep -rn '^[^#]*\bprint(' app/ --include="*.py" | grep -v '__main__\|# ok\|# debug\|test_' | wc -l)
if [ "$PRINTS" -gt 20 ]; then
    add_warning "print() found in ${PRINTS} locations in app/ (consider structlog)"
else
    add_ok "print() usage acceptable (${PRINTS})"
fi

# 4. SQL injection risk (string formatting in SQL)
echo "4. SQL injection..."
SQL_RISK=$(grep -rn "f\".*SELECT\|f\".*INSERT\|f\".*UPDATE\|f\".*DELETE\|\.format.*SELECT" app/ --include="*.py" | grep -v '# safe\|test_\|lessons_learned\|cost_tracker' | wc -l)
if [ "$SQL_RISK" -gt 0 ]; then
    add_warning "Potential SQL injection: ${SQL_RISK} f-string SQL queries found"
else
    add_ok "No obvious SQL injection risks"
fi

# 5. DB integrity
echo "5. DB integrity..."
ORPHANS=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "
SELECT
  (SELECT COUNT(*) FROM events e LEFT JOIN chunks c ON e.chunk_id=c.id WHERE c.id IS NULL AND e.chunk_id IS NOT NULL) +
  (SELECT COUNT(*) FROM chunk_entities ce LEFT JOIN chunks c ON ce.chunk_id=c.id WHERE c.id IS NULL) +
  (SELECT COUNT(*) FROM event_entities ee LEFT JOIN events e ON ee.event_id=e.id WHERE e.id IS NULL)
" 2>/dev/null || echo "0")
if [ "$ORPHANS" -gt 0 ] 2>/dev/null; then
    add_error "DB orphans found: ${ORPHANS} dangling references"
else
    add_ok "DB integrity: no orphans"
fi

# 6. Extraction workers health
echo "6. Extraction workers..."
WORKERS=$(ps aux | grep -E "extraction\.(entities|events)" | grep -v grep | wc -l)
if [ "$WORKERS" -eq 0 ]; then
    add_warning "No extraction workers running"
elif [ "$WORKERS" -gt 30 ]; then
    add_error "Too many workers: ${WORKERS} (risk connection overflow, max recommended: 24)"
else
    add_ok "Extraction workers: ${WORKERS}"
fi

# 7. Extraction coverage
echo "7. Extraction coverage..."
COVERAGE=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "
SELECT ROUND(100.0*(1-(SELECT COUNT(*) FROM chunks c LEFT JOIN events e ON e.chunk_id=c.id LEFT JOIN chunks_event_checked cec ON cec.chunk_id=c.id WHERE e.id IS NULL AND cec.chunk_id IS NULL)::numeric/GREATEST(COUNT(*),1)),1) FROM chunks
" 2>/dev/null || echo "0")
if [ "$(echo "$COVERAGE < 50" | bc)" -eq 1 ] 2>/dev/null; then
    add_warning "Event extraction coverage: ${COVERAGE}% (target: >90%)"
else
    add_ok "Event extraction coverage: ${COVERAGE}%"
fi

# 8. Disk space
echo "8. Disk space..."
DISK_PCT=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_PCT" -gt 90 ]; then
    add_error "Disk usage: ${DISK_PCT}% (critical)"
elif [ "$DISK_PCT" -gt 80 ]; then
    add_warning "Disk usage: ${DISK_PCT}%"
else
    add_ok "Disk usage: ${DISK_PCT}%"
fi

# 9. Docker services
echo "9. Docker services..."
PG_STATUS=$(docker inspect gilbertus-postgres --format='{{.State.Health.Status}}' 2>/dev/null || echo "down")
QD_STATUS=$(docker inspect gilbertus-qdrant --format='{{.State.Status}}' 2>/dev/null || echo "down")
WH_STATUS=$(docker inspect gilbertus-whisper --format='{{.State.Status}}' 2>/dev/null || echo "down")
if [ "$PG_STATUS" != "healthy" ]; then add_error "Postgres: ${PG_STATUS}"; else add_ok "Postgres: healthy"; fi
if [ "$QD_STATUS" != "running" ]; then add_error "Qdrant: ${QD_STATUS}"; else add_ok "Qdrant: running"; fi
if [ "$WH_STATUS" != "running" ]; then add_warning "Whisper: ${WH_STATUS}"; else add_ok "Whisper: running"; fi

# 10. Lessons learned compliance
echo "10. Lessons learned..."
LESSONS=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "SELECT COUNT(*) FROM lessons_learned" 2>/dev/null || echo "0")
add_ok "Lessons learned: ${LESSONS} rules"

# 11. API costs (last 24h)
echo "11. API costs..."
COST_24H=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "
SELECT COALESCE(ROUND(SUM(cost_usd)::numeric, 2), 0) FROM api_costs WHERE created_at > NOW() - INTERVAL '24 hours'
" 2>/dev/null || echo "0")
if [ "$(echo "$COST_24H > 50" | bc)" -eq 1 ] 2>/dev/null; then
    add_warning "API costs last 24h: \$${COST_24H} (high)"
else
    add_ok "API costs last 24h: \$${COST_24H}"
fi

# === REPORT ===
echo ""
echo "=== REPORT ==="
echo -e "$REPORT"
echo ""
echo "=== SUMMARY: ${ERRORS} errors, ${WARNINGS} warnings ==="

# Save to DB as insight if there are errors
if [ "$ERRORS" -gt 0 ]; then
    REPORT_ESCAPED=$(echo -e "$REPORT" | sed "s/'/''/g")
    docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "
    INSERT INTO insights (insight_type, area, title, description, confidence)
    VALUES ('code_quality', 'general',
            'Code Quality: ${ERRORS} errors, ${WARNINGS} warnings (${NOW})',
            '${REPORT_ESCAPED}', 0.9);" 2>/dev/null || true
    echo "Insight saved to DB."
fi

# 12. Non-regression check (Zasada Zero)
echo "12. Non-regression..."
BASELINE_FILE="logs/.qc_baseline.json"
CURRENT_MCP=$(echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","method":"tools/list","id":2,"params":{}}' | timeout 5 .venv/bin/python mcp_gilbertus/server.py 2>/dev/null | .venv/bin/python -c "
import sys
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    import json
    d=json.loads(line)
    if d.get('id')==2: print(len(d['result']['tools']))
" 2>/dev/null || echo "0")
CURRENT_CRON=$(crontab -l 2>/dev/null | grep -v "^#\|^$\|^TZ" | wc -l)
CURRENT_LESSONS=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "SELECT COUNT(*) FROM lessons_learned" 2>/dev/null || echo "0")
CURRENT_TABLES=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public'" 2>/dev/null || echo "0")

if [ -f "$BASELINE_FILE" ]; then
    PREV_MCP=$(.venv/bin/python -c "import json; print(json.load(open('$BASELINE_FILE')).get('mcp',0))" 2>/dev/null || echo "0")
    PREV_CRON=$(.venv/bin/python -c "import json; print(json.load(open('$BASELINE_FILE')).get('cron',0))" 2>/dev/null || echo "0")
    PREV_TABLES=$(.venv/bin/python -c "import json; print(json.load(open('$BASELINE_FILE')).get('tables',0))" 2>/dev/null || echo "0")
    PREV_LESSONS=$(.venv/bin/python -c "import json; print(json.load(open('$BASELINE_FILE')).get('lessons',0))" 2>/dev/null || echo "0")

    if [ "$CURRENT_MCP" -lt "$PREV_MCP" ] 2>/dev/null; then
        add_error "REGRESSION: MCP tools dropped from $PREV_MCP to $CURRENT_MCP"
    fi
    if [ "$CURRENT_CRON" -lt "$PREV_CRON" ] 2>/dev/null; then
        add_error "REGRESSION: Cron jobs dropped from $PREV_CRON to $CURRENT_CRON"
    fi
    if [ "$CURRENT_TABLES" -lt "$PREV_TABLES" ] 2>/dev/null; then
        add_error "REGRESSION: DB tables dropped from $PREV_TABLES to $CURRENT_TABLES"
    fi
    if [ "$CURRENT_LESSONS" -lt "$PREV_LESSONS" ] 2>/dev/null; then
        add_error "REGRESSION: Lessons learned dropped from $PREV_LESSONS to $CURRENT_LESSONS"
    fi
    if [ "$CURRENT_MCP" -ge "$PREV_MCP" ] && [ "$CURRENT_CRON" -ge "$PREV_CRON" ] && [ "$CURRENT_TABLES" -ge "$PREV_TABLES" ] 2>/dev/null; then
        add_ok "Non-regression: MCP=$CURRENT_MCP, Cron=$CURRENT_CRON, Tables=$CURRENT_TABLES, Lessons=$CURRENT_LESSONS"
    fi
else
    add_ok "Non-regression: baseline created (MCP=$CURRENT_MCP, Cron=$CURRENT_CRON, Tables=$CURRENT_TABLES)"
fi

# Save current as new baseline
echo "{\"mcp\":$CURRENT_MCP,\"cron\":$CURRENT_CRON,\"tables\":$CURRENT_TABLES,\"lessons\":$CURRENT_LESSONS,\"timestamp\":\"$NOW\"}" > "$BASELINE_FILE"

# Log
echo "=== Done: ${NOW} ===" >> logs/code_quality.log
echo -e "$REPORT" >> logs/code_quality.log
echo "" >> logs/code_quality.log
