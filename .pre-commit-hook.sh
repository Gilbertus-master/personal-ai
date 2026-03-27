#!/usr/bin/env bash
# Pre-commit hook for Gilbertus Albans
set -e
STAGED=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
if [ -z "$STAGED" ]; then exit 0; fi
ERRORS=0

# 1. Ruff check (ignore E402 — structlog/signal imports cause this)
echo "Running ruff check..."
if ! .venv/bin/ruff check --ignore E402 $STAGED 2>/dev/null; then
    echo "ERROR: ruff lint failed. Run: .venv/bin/ruff check --fix"
    ERRORS=$((ERRORS + 1))
fi

# 2. Raw psycopg.connect in app/ only (scripts are standalone)
echo "Checking for raw psycopg.connect in app/..."
for f in $STAGED; do
    if [[ "$f" == app/* ]] && grep -n 'psycopg\.connect(' "$f" 2>/dev/null | grep -v 'psycopg_pool\|# pool\|# noqa' > /dev/null; then
        echo "ERROR: $f uses raw psycopg.connect()"
        ERRORS=$((ERRORS + 1))
    fi
done

# 3. Non-regression baseline check (ZASADA ZERO)
BASELINE_FILE="logs/.qc_baseline.json"
if [ -f "$BASELINE_FILE" ]; then
    CURRENT_MCP=$(grep -c 'Tool(name=' mcp_gilbertus/server.py 2>/dev/null || echo 0)
    BASE_MCP=$(python3 -c "import json; print(json.load(open('$BASELINE_FILE')).get('mcp',0))" 2>/dev/null || echo 0)

    CURRENT_TABLES=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -tAc \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null || echo 0)
    BASE_TABLES=$(python3 -c "import json; print(json.load(open('$BASELINE_FILE')).get('tables',0))" 2>/dev/null || echo 0)

    if [ "$CURRENT_MCP" -lt "$BASE_MCP" ] 2>/dev/null; then
        echo "❌ NON-REGRESSION: MCP tools dropped: $CURRENT_MCP < baseline $BASE_MCP"
        ERRORS=$((ERRORS + 1))
    fi
    if [ "$CURRENT_TABLES" -lt "$BASE_TABLES" ] 2>/dev/null; then
        echo "❌ NON-REGRESSION: DB tables dropped: $CURRENT_TABLES < baseline $BASE_TABLES"
        ERRORS=$((ERRORS + 1))
    fi
fi

if [ $ERRORS -gt 0 ]; then
    echo "Pre-commit: $ERRORS error(s)."
    exit 1
fi
echo "Pre-commit: OK"
