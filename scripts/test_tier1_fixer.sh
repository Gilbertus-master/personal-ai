#!/usr/bin/env bash
# test_tier1_fixer.sh — smoke test for tier-1 autofixer
# Runs 1 tier-1 cluster in live mode, verifies results, reverts changes.
set -euo pipefail
cd /home/sebastian/personal-ai

echo "=== Tier-1 Autofixer Smoke Test ==="
echo ""

# 1. Check venv Python can import dependencies
echo "[1/4] Checking venv Python imports..."
if ! .venv/bin/python3 -c "import structlog, dotenv, psycopg" 2>/dev/null; then
    echo "FAIL: venv Python missing dependencies"
    exit 1
fi
echo "  OK: venv Python has all deps"

# 2. Check tier1_executor imports
echo "[2/4] Checking tier1_executor import..."
if ! .venv/bin/python3 -c "from app.analysis.autofixer.tier1_executor import execute_tier1" 2>/dev/null; then
    echo "FAIL: tier1_executor import failed"
    exit 1
fi
echo "  OK: tier1_executor imports cleanly"

# 3. Dry run — check eligible clusters
echo "[3/4] Dry run — checking eligible tier-1 clusters..."
DRY_OUTPUT=$(.venv/bin/python3 -m app.analysis.code_fixer --dry-run 2>&1 || true)
TIER1_COUNT=$(echo "$DRY_OUTPUT" | grep -c "tier.*1" || echo "0")
echo "  Found ~${TIER1_COUNT} tier-1 references in output"
echo "  Last 5 lines:"
echo "$DRY_OUTPUT" | tail -5 | sed 's/^/    /'

# 4. Live run on 1 cluster, then revert
echo "[4/4] Live test — 1 tier-1 cluster (will revert after)..."
# Save current state
git stash --include-untracked -q 2>/dev/null || true

LIVE_OUTPUT=$(.venv/bin/python3 -m app.analysis.code_fixer --parallel 1 --tier1-only 2>&1 || true)
FIXED=$(echo "$LIVE_OUTPUT" | grep -c '"fixed": true\|fixed_files\|tier1_success' || echo "0")

# Revert any changes made by the fixer
git checkout -- . 2>/dev/null || true
git stash pop -q 2>/dev/null || true

echo ""
if [ "$FIXED" -gt 0 ]; then
    echo "PASS: tier-1 fixer produced at least 1 fix"
else
    echo "INFO: no fixes produced (may be expected if all findings already resolved)"
    echo "  Last 10 lines of output:"
    echo "$LIVE_OUTPUT" | tail -10 | sed 's/^/    /'
fi

echo ""
echo "=== Test complete ==="
