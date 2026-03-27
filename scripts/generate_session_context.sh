#!/usr/bin/env bash
# Generate SESSION_CONTEXT.md — fresh snapshot of system state for Claude Code sessions.
# Run: bash scripts/generate_session_context.sh
# Cron: */30 * * * * cd /home/sebastian/personal-ai && bash scripts/generate_session_context.sh
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="SESSION_CONTEXT.md"
NOW_CET=$(TZ=Europe/Warsaw date '+%Y-%m-%d %H:%M:%S %Z')
NOW_UTC=$(date -u '+%Y-%m-%d %H:%M:%S UTC')

cat > "$OUT" <<HEADER
# Session Context — Auto-generated
**Generated:** ${NOW_CET} (${NOW_UTC})
**Project:** Gilbertus Albans (personal-ai)
**Plan:** ~/.claude/plans/effervescent-squishing-sky.md

HEADER

# DB stats
echo "## Database Stats" >> "$OUT"
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "
SELECT 'chunks,' || COUNT(*) FROM chunks
UNION ALL SELECT 'documents,' || COUNT(*) FROM documents
UNION ALL SELECT 'entities,' || COUNT(*) FROM entities
UNION ALL SELECT 'events,' || COUNT(*) FROM events
UNION ALL SELECT 'insights,' || COUNT(*) FROM insights
UNION ALL SELECT 'decisions,' || COUNT(*) FROM decisions
UNION ALL SELECT 'people,' || COUNT(*) FROM people
UNION ALL SELECT 'alerts,' || COUNT(*) FROM alerts
UNION ALL SELECT 'summaries,' || COUNT(*) FROM summaries
ORDER BY 1;
" 2>/dev/null | while IFS=',' read -r name count; do
    echo "- **${name}:** ${count}" >> "$OUT"
done

# Extraction coverage
echo "" >> "$OUT"
echo "## Extraction Coverage" >> "$OUT"
COVERAGE=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "
SELECT
  (SELECT COUNT(*) FROM chunks),
  (SELECT COUNT(*) FROM chunks c LEFT JOIN events e ON e.chunk_id=c.id LEFT JOIN chunks_event_checked cec ON cec.chunk_id=c.id WHERE e.id IS NULL AND cec.chunk_id IS NULL),
  (SELECT COUNT(*) FROM chunks c LEFT JOIN chunk_entities ce ON ce.chunk_id=c.id LEFT JOIN chunks_entity_checked cec ON cec.chunk_id=c.id WHERE ce.id IS NULL AND cec.chunk_id IS NULL);
" 2>/dev/null || echo "0|0|0")
total=$(echo "$COVERAGE" | cut -d'|' -f1)
rev=$(echo "$COVERAGE" | cut -d'|' -f2)
ren=$(echo "$COVERAGE" | cut -d'|' -f3)
if [ "$total" -gt 0 ] 2>/dev/null; then
    pct_ev=$(echo "scale=1; (1 - $rev / $total) * 100" | bc 2>/dev/null || echo "?")
    pct_en=$(echo "scale=1; (1 - $ren / $total) * 100" | bc 2>/dev/null || echo "?")
    echo "- Events: ${pct_ev}% covered (${rev} remaining)" >> "$OUT"
    echo "- Entities: ${pct_en}% covered (${ren} remaining)" >> "$OUT"
else
    echo "- Coverage: unable to calculate" >> "$OUT"
fi

# Last syncs
echo "" >> "$OUT"
echo "## Last Syncs" >> "$OUT"
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "
SELECT source_type || ',' || MAX(imported_at)::text FROM sources GROUP BY source_type ORDER BY MAX(imported_at) DESC;
" 2>/dev/null | while IFS=',' read -r src ts; do
    echo "- **${src}:** ${ts}" >> "$OUT"
done

# Running workers
echo "" >> "$OUT"
echo "## Running Processes" >> "$OUT"
WORKERS=$(ps aux | grep -E "extraction\.(entities|events)" | grep -v grep | wc -l)
echo "- Extraction workers: ${WORKERS}" >> "$OUT"

# Git status
echo "" >> "$OUT"
echo "## Git" >> "$OUT"
echo "- Branch: $(git branch --show-current 2>/dev/null || echo 'unknown')" >> "$OUT"
echo "- Last commit: $(git log --oneline -1 2>/dev/null || echo 'unknown')" >> "$OUT"
CHANGES=$(git status --porcelain 2>/dev/null | wc -l)
echo "- Uncommitted changes: ${CHANGES} files" >> "$OUT"

echo "" >> "$OUT"
echo "---" >> "$OUT"
echo "*Read the plan at ~/.claude/plans/effervescent-squishing-sky.md for full context.*" >> "$OUT"

# Exit here — inventory section runs separately to avoid pipefail issues
exit 0

# Inventory of achievements (auto-updated)
echo "" >> "$OUT"
echo "## Achievement Inventory (non-regression baseline)" >> "$OUT"

# Counts
MCP_COUNT=$(echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","method":"tools/list","id":2,"params":{}}' | timeout 5 .venv/bin/python mcp_gilbertus/server.py 2>/dev/null | .venv/bin/python -c "
import sys
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    import json
    d = json.loads(line)
    if d.get('id') == 2:
        print(len(d['result']['tools']))
" 2>/dev/null || echo "?")

CRON_COUNT=$(crontab -l 2>/dev/null | grep -v "^#\|^$\|^TZ" | wc -l)
LESSONS_COUNT=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "SELECT COUNT(*) FROM lessons_learned" 2>/dev/null || echo "?")
TABLE_COUNT=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -t -A -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname='public'" 2>/dev/null || echo "?")
MODULE_COUNT=$(find app/ -name "*.py" -not -name "__init__.py" -not -path "*__pycache__*" 2>/dev/null | wc -l)
SCRIPT_COUNT=$(ls scripts/*.sh scripts/*.py 2>/dev/null | wc -l)
MEMORY_COUNT=$(ls ~/.claude/projects/-home-sebastian-personal-ai/memory/*.md 2>/dev/null | wc -l)

echo "- MCP tools: ${MCP_COUNT}" >> "$OUT"
echo "- Cron jobs: ${CRON_COUNT}" >> "$OUT"
echo "- Lessons learned: ${LESSONS_COUNT}" >> "$OUT"
echo "- DB tables: ${TABLE_COUNT}" >> "$OUT"
echo "- App modules: ${MODULE_COUNT}" >> "$OUT"
echo "- Scripts: ${SCRIPT_COUNT}" >> "$OUT"
echo "- Memory files: ${MEMORY_COUNT}" >> "$OUT"
echo "- CLAUDE.md: $(test -f CLAUDE.md && echo 'OK' || echo 'MISSING')" >> "$OUT"
echo "- Pre-commit hook: $(test -f .git/hooks/pre-commit && echo 'OK' || echo 'MISSING')" >> "$OUT"
