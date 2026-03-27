#!/usr/bin/env bash
# generate_inventory.sh — Auto-generate achievement inventory for non-regression checks.
# Appends to SESSION_CONTEXT.md. Run after generate_session_context.sh.
cd "$(dirname "$0")/.."

OUT="SESSION_CONTEXT.md"

echo "" >> "$OUT"
echo "## Achievement Inventory (non-regression baseline)" >> "$OUT"

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
echo "" >> "$OUT"
echo "**ZASADA ZERO: Nowe developmenty NIE MOGA zmniejszyc tych liczb.**" >> "$OUT"
