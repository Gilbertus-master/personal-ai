#!/usr/bin/env bash
# Repair Process Orchestrator — analyzes and improves the 3-layer repair system
# Usage: bash scripts/run_repair_orchestrator.sh
set -euo pipefail

PROJ=/home/sebastian/personal-ai
PROMPT="$PROJ/scripts/repair_orchestrator_prompt.md"
LOG="$PROJ/logs/repair_orchestrator.log"
CLAUDE_BIN="${CLAUDE_BIN:-/home/sebastian/.npm-global/bin/claude}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "=== Repair Orchestrator — start ==="

# Pre-flight: show current state
log "Current open findings:"
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "
SELECT category, COUNT(*) as open,
  SUM(CASE WHEN fix_attempt_count >= 2 THEN 1 ELSE 0 END) as stuck
FROM code_review_findings WHERE NOT resolved
GROUP BY category ORDER BY open DESC;
" 2>&1 | tee -a "$LOG"

# Run the orchestrator
log "Launching Claude orchestrator session..."
cd "$PROJ"

$CLAUDE_BIN --dangerously-skip-permissions --print --max-turns 30 \
  "$(cat <<'ORCHESTRATOR_PROMPT'
You are the Repair Process Orchestrator for the Gilbertus AI project.

Read the improvement plan in scripts/repair_orchestrator_prompt.md and implement ALL 6 fixes in priority order.

## Your tasks:

### 1. Fix _verify_fix() in app/analysis/autofixer/tier2_executor.py
Replace the current _verify_fix() function with baseline comparison logic:
- Before checking ruff, stash changes to get baseline error count
- After unstashing, get new error count
- Only fail if fix INTRODUCED new errors (after > before)
- Add helper function _count_ruff_errors()
- KEEP the git diff check (no changes = fail)

### 2. Add sanitize_hotspot_files() to app/analysis/code_fixer.py
- Query DB for files with 5+ stuck findings (fix_attempt_count >= 2)
- Run ruff --fix on each
- Git commit the cleanup
- Call this at the start of run_parallel()

### 3. Lower tier 3 promotion threshold in app/analysis/autofixer/tier3_deep_fixer.py
- Change MIN_ATTEMPTS_FOR_PROMOTION from 3 to 2

### 4. Exclude improvement category in app/analysis/autofixer/cluster_manager.py
- In the query that fetches unresolved findings, add: AND category != 'improvement'
- Mark existing improvement findings as manual_review = TRUE

### 5. Add consecutive failure tracking to scripts/webapp_autofix.sh
- Track consecutive server failures in state JSON
- After 5 consecutive failures, log warning and exit (don't keep restarting)
- Reset counter on successful check

### 6. Verify all changes
- Run: ruff check on all modified files
- Run: python -c "from app.analysis.autofixer.tier2_executor import _verify_fix; print('OK')"
- Run: python -c "from app.analysis.autofixer.tier3_deep_fixer import MIN_ATTEMPTS_FOR_PROMOTION; assert MIN_ATTEMPTS_FOR_PROMOTION == 2"
- Git commit all changes with message: "fix(repair): improve 3-layer repair pipeline — baseline verification, hotspot sanitizer, tier3 threshold"

## Rules:
- Read each file BEFORE editing
- Use parameterized SQL (never f-strings with user input)
- Use structlog for logging (never print())
- Use get_pg_connection() from app.db.postgres (never raw psycopg)
- Test imports after changes
- Do NOT change business logic — only fix the repair pipeline
ORCHESTRATOR_PROMPT
)" 2>&1 | tee -a "$LOG"

exit_code=$?

log "Orchestrator exit code: $exit_code"

# Post-flight: verify
log "Post-flight verification..."
cd "$PROJ"
.venv/bin/python -c "
from app.analysis.autofixer.tier2_executor import _verify_fix, _count_ruff_errors
print('✅ tier2_executor imports OK')
" 2>&1 | tee -a "$LOG" || log "❌ tier2_executor import failed"

.venv/bin/python -c "
from app.analysis.autofixer.tier3_deep_fixer import MIN_ATTEMPTS_FOR_PROMOTION
assert MIN_ATTEMPTS_FOR_PROMOTION == 2, f'Expected 2, got {MIN_ATTEMPTS_FOR_PROMOTION}'
print('✅ tier3 threshold = 2')
" 2>&1 | tee -a "$LOG" || log "❌ tier3 threshold check failed"

docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "
SELECT 'open' as status, COUNT(*) FROM code_review_findings WHERE NOT resolved
UNION ALL
SELECT 'stuck', COUNT(*) FROM code_review_findings WHERE NOT resolved AND fix_attempt_count >= 2
UNION ALL
SELECT 'manual_review', COUNT(*) FROM code_review_findings WHERE manual_review
UNION ALL
SELECT 'improvement_excluded', COUNT(*) FROM code_review_findings WHERE category = 'improvement' AND manual_review;
" 2>&1 | tee -a "$LOG"

log "=== Repair Orchestrator — done ==="
