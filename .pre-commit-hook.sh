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

if [ $ERRORS -gt 0 ]; then
    echo "Pre-commit: $ERRORS error(s)."
    exit 1
fi
echo "Pre-commit: OK"
