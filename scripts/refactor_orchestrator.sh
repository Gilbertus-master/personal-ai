#!/usr/bin/env bash
# Code Refactoring Orchestrator — systematic refactoring with non-regression guarantee
set -euo pipefail

PROJ=/home/sebastian/personal-ai
LOG="$PROJ/logs/refactor_orchestrator.log"
CLAUDE_BIN="${CLAUDE_BIN:-/home/sebastian/.npm-global/bin/claude}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }
mkdir -p "$PROJ/logs"

LOCKFILE="/tmp/refactor_orchestrator.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  log "Already running, exiting"
  exit 0
fi
trap 'rm -f $LOCKFILE' EXIT INT TERM

log "=== Refactoring Orchestrator — start ==="

# ── Phase 1: Pre-refactoring baseline ───────────────────────────────────
log "Phase 1: Capturing non-regression baseline..."

cd "$PROJ"

# API health
API_HEALTH=""
for ep in /status /brief/today /alerts /admin/roles /autofixers/dashboard /crons/summary /costs/budget /people /commitments /compliance/dashboard; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://127.0.0.1:8000${ep}" 2>/dev/null || true)
  API_HEALTH="${API_HEALTH}\n${ep} → ${code}"
done
log "API baseline captured"

# DB stats
DB_STATS=$(docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "
SELECT 'documents' as t, COUNT(*) as n FROM documents
UNION ALL SELECT 'chunks', COUNT(*) FROM chunks
UNION ALL SELECT 'entities', COUNT(*) FROM entities
UNION ALL SELECT 'events', COUNT(*) FROM events
UNION ALL SELECT 'code_review_findings', COUNT(*) FROM code_review_findings
ORDER BY t;" 2>/dev/null)
log "DB baseline captured"

# Ruff baseline
RUFF_BASELINE=$(.venv/bin/ruff check app/ mcp_gilbertus/ 2>/dev/null | tail -1)
log "Ruff baseline: $RUFF_BASELINE"

# Import check baseline
IMPORT_BASELINE=$(.venv/bin/python -c "
import os, importlib, sys
sys.path.insert(0, '.')
failed = 0
checked = 0
for root, dirs, files in os.walk('app'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if not f.endswith('.py') or f == '__init__.py': continue
        mod = os.path.join(root, f).replace('/', '.').replace('.py', '')
        checked += 1
        try: importlib.import_module(mod)
        except: failed += 1
print(f'{checked} modules, {failed} failed')
" 2>&1 | tail -1)
log "Import baseline: $IMPORT_BASELINE"

# Cron count
CRON_COUNT=$(crontab -l 2>/dev/null | grep -v "^#" | grep -v "^$" | wc -l || true)
log "Cron baseline: $CRON_COUNT jobs"

# Frontend pages
FRONTEND_PAGES=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://172.17.44.2:3000/dashboard" 2>/dev/null || true)
log "Frontend baseline: dashboard=$FRONTEND_PAGES"

# ── Phase 2: Run refactoring ────────────────────────────────────────────
log "Phase 2: Launching Claude refactoring session..."

timeout 3600 $CLAUDE_BIN --dangerously-skip-permissions --print --max-turns 80 \
"You are performing a systematic code refactoring of the Gilbertus project.

## NON-REGRESSION BASELINE (MUST preserve)
API endpoints:$(echo -e "$API_HEALTH")
DB stats:
$DB_STATS
Ruff: $RUFF_BASELINE
Imports: $IMPORT_BASELINE
Crons: $CRON_COUNT active
Frontend: dashboard=$FRONTEND_PAGES

## REFACTORING RULES
1. **Non-regression is absolute** — after EVERY change, verify:
   - Imports still work: python -c 'import app.MODULE'
   - Ruff passes: ruff check FILE
   - API returns same status codes
2. **One file at a time** — read, refactor, verify, move to next
3. **Never change business logic** — only improve code quality
4. **Never change DB schema** — only improve queries
5. **Never change API contracts** — same endpoints, same response shapes
6. **Commit after each logical group** — small, reviewable commits

## REFACTORING PRIORITIES (in order)

### Priority 1: Remove dead code and backup files
Find and remove:
- All .bak, .backup, .orig, .backup2, .original files in app/
- Unused imports (ruff --fix --select F401)
- Commented-out code blocks (>5 lines of # old code)
- Unused functions (grep for def NAME and check if NAME is called anywhere)

Run: find app/ -name '*.bak' -o -name '*.backup' -o -name '*.orig' -o -name '*.backup2' -o -name '*.original' | head -20
Delete them. Also check root dir for stale scripts: fix_exceptions.py, fix_n1.py, etc.

Commit: 'refactor: remove dead code, backup files, and unused imports'

### Priority 2: Consolidate duplicate patterns
Find repeated patterns and extract to shared utilities:

a) **DB connection pattern** — many files do:
   \`\`\`python
   with get_pg_connection() as conn:
       with conn.cursor() as cur:
           cur.execute(...)
           rows = cur.fetchall()
   \`\`\`
   Check if there's a simpler helper already in app/db/ that could reduce boilerplate.

b) **Anthropic API call pattern** — many files create client, call, log cost.
   Check if app/db/cost_tracker.py or similar already provides a wrapper.
   If not, don't create one — just document the pattern.

c) **datetime.now() with timezone** — verify all use app.config.timezone.now() after the timezone refactor.

Only extract if the pattern appears 5+ times and extraction is clean.

Commit: 'refactor: consolidate repeated patterns'

### Priority 3: Fix code quality issues found by ruff
Run: ruff check app/ --select E,W,F --statistics
Fix the top categories:
- F841: unused variables
- E711: comparison to None (use 'is None')
- E712: comparison to True/False
- W291: trailing whitespace
- F401: unused imports (already handled in P1)

Use: ruff check --fix --select F841,E711,E712,W291 app/
Verify: ruff check app/

Commit: 'refactor: fix ruff warnings (unused vars, None comparisons, whitespace)'

### Priority 4: Improve error handling in critical paths
Check these critical files for bare except/pass patterns:
- app/api/main.py
- app/retrieval/answering.py
- app/extraction/entities.py
- app/extraction/events.py
- app/orchestrator/task_monitor.py

Replace bare \`except:\` or \`except Exception: pass\` with:
\`\`\`python
except Exception:
    log.exception('descriptive_error_name')
\`\`\`
Only fix truly silent error swallowing. Don't add logging to intentional silencing (e.g., catch-and-continue loops).

Commit: 'refactor: replace bare except:pass with structured logging'

### Priority 5: Standardize structlog usage
Find remaining print() calls in production code (not __main__ blocks):
Run: grep -rn 'print(' app/ --include='*.py' | grep -v __pycache__ | grep -v '__main__' | grep -v '# ' | head -20

Replace with structlog:
\`\`\`python
import structlog
log = structlog.get_logger(__name__)
# print(f'Processing {x}') → log.info('processing', item=x)
\`\`\`

Commit: 'refactor: replace print() with structlog in production code'

### Priority 6: Type hints for public functions
Add type hints to functions in:
- app/api/main.py (top 10 most used endpoints)
- app/retrieval/answering.py
- app/db/postgres.py

Only add return types and parameter types. Don't refactor function bodies.

Commit: 'refactor: add type hints to core public functions'

## AFTER ALL REFACTORING — NON-REGRESSION CHECK

Run these checks and report results:

1. Import check:
   python -c \"
   import os, importlib, sys
   sys.path.insert(0, '.')
   failed = []
   for root, dirs, files in os.walk('app'):
       dirs[:] = [d for d in dirs if d != '__pycache__']
       for f in files:
           if not f.endswith('.py') or f == '__init__.py': continue
           mod = os.path.join(root, f).replace('/', '.').replace('.py', '')
           try: importlib.import_module(mod)
           except Exception as e: failed.append(f'{mod}: {e}')
   print(f'Failed: {len(failed)}')
   for f in failed: print(f)
   \"

2. Ruff check: ruff check app/ mcp_gilbertus/

3. API health:
   for ep in /status /brief/today /alerts /admin/roles; do
     curl -s -o /dev/null -w \"%{http_code} \$ep\" http://127.0.0.1:8000\$ep
   done

4. Compare results with baseline above. If anything regressed → REVERT that change.

## CONSTRAINTS
- Do NOT touch frontend code (TypeScript/React)
- Do NOT touch database migrations
- Do NOT change .env or credentials
- Do NOT modify cron schedules
- Use parameterized SQL always
- Use get_pg_connection() from app.db.postgres always
- Maximum 6 commits total
" 2>&1 | tee -a "$LOG"
CLAUDE_EXIT=${PIPESTATUS[0]}

log "Refactoring exit code: $CLAUDE_EXIT"
if [ "$CLAUDE_EXIT" -eq 124 ]; then
  log "❌ Claude session timed out after 1h — aborting post-check"
  exit 1
fi
if [ "$CLAUDE_EXIT" -ne 0 ]; then
  log "❌ Claude session failed — aborting post-check"
  exit 1
fi

# ── Phase 3: Post-refactoring verification ──────────────────────────────
log "Phase 3: Post-refactoring non-regression check..."

# Initialize regression flag
REGRESSION=0

# API health post-check
POST_API=""
for ep in /status /brief/today /alerts /admin/roles /autofixers/dashboard /crons/summary /costs/budget /people /commitments /compliance/dashboard; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://127.0.0.1:8000${ep}" 2>/dev/null || true)
  POST_API="${POST_API}\n${ep} → ${code}"
done
log "Post API:$(echo -e "$POST_API")"

# Compare API health against baseline
while IFS= read -r baseline_line; do
  [ -z "$baseline_line" ] && continue
  baseline_ep=$(echo "$baseline_line" | cut -d' ' -f1)
  baseline_code=$(echo "$baseline_line" | cut -d' ' -f3)
  post_code=$(echo -e "$POST_API" | grep "^${baseline_ep} " | cut -d' ' -f3)
  if [ -n "$post_code" ] && [ "$post_code" != "$baseline_code" ]; then
    log "❌ REGRESSION: $baseline_ep changed from $baseline_code to $post_code"
    REGRESSION=1
  fi
done <<< "$(echo -e "$API_HEALTH")"

# Ruff post-check
POST_RUFF=$(.venv/bin/ruff check app/ mcp_gilbertus/ 2>/dev/null | tail -1)
log "Post ruff: $POST_RUFF"

# Import post-check
POST_IMPORTS=$(.venv/bin/python -c "
import os, importlib, sys
sys.path.insert(0, '.')
failed = 0
for root, dirs, files in os.walk('app'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if not f.endswith('.py') or f == '__init__.py': continue
        mod = os.path.join(root, f).replace('/', '.').replace('.py', '')
        try: importlib.import_module(mod)
        except: failed += 1
print(f'{failed} failed')
" 2>&1 | tail -1)
log "Post imports: $POST_IMPORTS"

# Compare import failures against baseline
BASELINE_FAIL=$(echo "$IMPORT_BASELINE" | awk '{print $(NF-1)}')
POST_FAIL=$(echo "$POST_IMPORTS" | awk '{print $1}')
if [ "$POST_FAIL" -gt "$BASELINE_FAIL" ]; then
  log "❌ REGRESSION: imports failed $BASELINE_FAIL→$POST_FAIL"
  REGRESSION=1
fi

# Cron post-check
POST_CRONS=$(crontab -l 2>/dev/null | grep -v "^#" | grep -v "^$" | wc -l || true)
log "Post crons: $POST_CRONS (baseline: $CRON_COUNT)"

if [ "$POST_CRONS" -lt "$CRON_COUNT" ]; then
  log "❌ REGRESSION: cron count dropped from $CRON_COUNT to $POST_CRONS"
  REGRESSION=1
fi

log "=== Refactoring Orchestrator — done ==="

if [ "$REGRESSION" -eq 1 ]; then
  log "❌ Non-regression check FAILED — regressions detected"
  exit 1
fi

log "✅ All non-regression checks passed"
exit 0
