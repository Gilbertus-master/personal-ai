#!/usr/bin/env bash
# Architecture Review Agent — weekly automated analysis.
# Cron: 0 22 * * 0 (Sundays 22:00 CET, before Monday morning brief)
set -uo pipefail
cd "$(dirname "$0")/.."

NOW=$(TZ=Europe/Warsaw date '+%Y-%m-%d %H:%M %Z')
REPORT=""
ISSUES=0

add_issue() { ISSUES=$((ISSUES + 1)); REPORT="${REPORT}\n[ISSUE] $1"; }
add_ok() { REPORT="${REPORT}\n[OK] $1"; }

echo "=== Architecture Review: ${NOW} ==="

# 1. Module coupling violations
echo "1. Module coupling..."
BAD_IMPORTS=$(grep -rn "from app.retrieval\|from app.api" app/ingestion/ app/extraction/ app/db/ --include="*.py" 2>/dev/null | grep -v __pycache__ | grep -v "app.api.schemas\|app.db\." | wc -l)
if [ "$BAD_IMPORTS" -gt 0 ]; then
    add_issue "Module coupling: $BAD_IMPORTS forbidden cross-imports"
else
    add_ok "Module boundaries respected"
fi

# 2. API latency trend (this week vs last week)
echo "2. API latency..."
THIS_WEEK=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "
SELECT ROUND(AVG(latency_ms)) FROM ask_runs WHERE created_at > NOW() - INTERVAL '7 days'" 2>/dev/null || echo "0")
LAST_WEEK=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "
SELECT ROUND(AVG(latency_ms)) FROM ask_runs WHERE created_at > NOW() - INTERVAL '14 days' AND created_at < NOW() - INTERVAL '7 days'" 2>/dev/null || echo "0")
if [ -n "$THIS_WEEK" ] && [ -n "$LAST_WEEK" ] && [ "$LAST_WEEK" != "" ] && [ "$LAST_WEEK" != "0" ] 2>/dev/null; then
    CHANGE=$(echo "scale=0; ($THIS_WEEK - $LAST_WEEK) * 100 / $LAST_WEEK" | bc 2>/dev/null || echo "0")
    if [ "$CHANGE" -gt 20 ] 2>/dev/null; then
        add_issue "Latency regression: ${THIS_WEEK}ms this week vs ${LAST_WEEK}ms last (${CHANGE}% increase)"
    else
        add_ok "API latency: ${THIS_WEEK}ms (change: ${CHANGE}%)"
    fi
else
    add_ok "API latency: ${THIS_WEEK}ms (no comparison data)"
fi

# 3. Tech debt trend
echo "3. Tech debt..."
TODOS=$(grep -rn "TODO\|FIXME\|HACK\|XXX" app/ --include="*.py" 2>/dev/null | grep -v __pycache__ | wc -l)
add_ok "Tech debt markers: $TODOS"

# 4. Ruff errors trend
echo "4. Code quality..."
RUFF_ERRORS=$(.venv/bin/ruff check app/ 2>/dev/null | grep "^Found" | head -1 | grep -oP '^\d+' || echo "0")
if [ "$RUFF_ERRORS" -gt 50 ] 2>/dev/null; then
    add_issue "Ruff errors: $RUFF_ERRORS (growing)"
else
    add_ok "Ruff errors: $RUFF_ERRORS"
fi

# 5. DB table count (detect schema drift)
echo "5. Schema drift..."
TABLE_COUNT=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public'" 2>/dev/null || echo "0")
add_ok "Tables: $TABLE_COUNT"

# 6. Qdrant sync check
echo "6. Qdrant sync..."
QDRANT=$(curl -s http://localhost:6333/collections/gilbertus_chunks 2>/dev/null | .venv/bin/python -c "import sys,json; print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null || echo "0")
PG_EMBEDDED=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "SELECT COUNT(*) FROM chunks WHERE embedding_status='done'" 2>/dev/null || echo "0")
DRIFT=$((QDRANT - PG_EMBEDDED))
if [ "$DRIFT" -gt 1000 ] || [ "$DRIFT" -lt -1000 ] 2>/dev/null; then
    add_issue "Qdrant drift: $QDRANT vectors vs $PG_EMBEDDED embedded (diff: $DRIFT)"
else
    add_ok "Qdrant in sync: $QDRANT vectors, $PG_EMBEDDED embedded (diff: $DRIFT)"
fi

# 7. API cost trend (this week)
echo "7. API costs..."
WEEK_COST=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "
SELECT ROUND(SUM(cost_usd)::numeric, 2) FROM api_costs WHERE created_at > NOW() - INTERVAL '7 days'" 2>/dev/null || echo "0")
add_ok "API costs this week: \$${WEEK_COST}"

# 8. Lessons learned count
echo "8. Lessons learned..."
LESSONS=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "SELECT COUNT(*) FROM lessons_learned" 2>/dev/null || echo "0")
add_ok "Lessons learned: $LESSONS"

# 9. Extraction coverage
echo "9. Extraction..."
EV_COV=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "
SELECT ROUND(100.0*(1-(SELECT COUNT(*) FROM chunks c LEFT JOIN events e ON e.chunk_id=c.id LEFT JOIN chunks_event_checked cec ON cec.chunk_id=c.id WHERE e.id IS NULL AND cec.chunk_id IS NULL)::numeric/GREATEST(COUNT(*),1)),1) FROM chunks" 2>/dev/null || echo "0")
add_ok "Event coverage: ${EV_COV}%"

# 10. Feedback quality (if any)
echo "10. Feedback..."
FEEDBACK=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "SELECT COUNT(*) FROM response_feedback" 2>/dev/null || echo "0")
POSITIVE=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "SELECT COUNT(*) FROM response_feedback WHERE rating > 0" 2>/dev/null || echo "0")
add_ok "Feedback: $FEEDBACK total, $POSITIVE positive"

# === REPORT ===
echo ""
echo "=== WEEKLY ARCHITECTURE REPORT ==="
echo -e "$REPORT"
echo ""
echo "=== SUMMARY: ${ISSUES} issues ==="

# Save as insight
if [ "$ISSUES" -gt 0 ]; then
    REPORT_ESCAPED=$(echo -e "$REPORT" | sed "s/'/''/g")
    docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "
    INSERT INTO insights (insight_type, area, title, description, confidence)
    VALUES ('architecture_review', 'general',
            'Architecture Review: ${ISSUES} issues (${NOW})',
            '${REPORT_ESCAPED}', 0.9);" 2>/dev/null || true
fi

echo "=== Done ===" >> logs/architecture_review.log
echo -e "$REPORT" >> logs/architecture_review.log
echo "" >> logs/architecture_review.log
