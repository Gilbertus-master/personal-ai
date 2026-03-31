#!/usr/bin/env bash
# Timezone Centralization Orchestrator
# Replaces all hardcoded UTC/CET references with central APP_TIMEZONE config
set -euo pipefail

PROJ=/home/sebastian/personal-ai
LOG="$PROJ/logs/timezone_orchestrator.log"
CLAUDE_BIN="${CLAUDE_BIN:-/home/sebastian/.npm-global/bin/claude}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }
mkdir -p "$PROJ/logs"
[[ -x "$CLAUDE_BIN" ]] || { log "ERROR: claude binary not found at $CLAUDE_BIN"; exit 1; }

LOCK=/tmp/timezone_orchestrator.lock
exec 9>"$LOCK"
flock -n 9 || { log "Already running — aborting"; exit 1; }

trap 'log "Killed by timeout/signal"' TERM INT EXIT

log "=== Timezone Centralization Orchestrator — start ==="
cd "$PROJ"

timeout 3600 $CLAUDE_BIN --dangerously-skip-permissions --print --max-turns 80 \
"You are centralizing timezone handling across the Gilbertus project.

## GOAL
Create ONE central timezone config and replace ALL hardcoded timezone references.
After this, changing timezone requires editing ONE file only.

## STEP 1: Create central timezone config
Create file: app/config/timezone.py

\`\`\`python
\"\"\"Central timezone configuration for Gilbertus.

Change APP_TIMEZONE here to update timezone across the entire system.
All modules import from this file — never hardcode timezone elsewhere.
\"\"\"
from zoneinfo import ZoneInfo

APP_TIMEZONE_NAME = 'Europe/Warsaw'  # CET/CEST
APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)

def now():
    \"\"\"Current datetime in app timezone (CET).\"\"\"
    from datetime import datetime
    return datetime.now(APP_TIMEZONE)

def today():
    \"\"\"Current date in app timezone (CET).\"\"\"
    return now().date()

def to_app_tz(dt):
    \"\"\"Convert any datetime to app timezone.\"\"\"
    if dt is None:
        return None
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(APP_TIMEZONE)
\`\`\`

Make sure the directory app/config/ exists (create __init__.py if needed).

## STEP 2: Fix the 3 broken CET definitions (HIGH PRIORITY)
These files use \`CET = timezone(timedelta(hours=1))\` which IGNORES DST:

1. app/analysis/relationship/event_tracker.py — line 12
2. app/analysis/relationship/pattern_detector.py — line 10
3. app/analysis/relationship/coach.py — line 16

Replace with:
\`\`\`python
from app.config.timezone import APP_TIMEZONE as CET
\`\`\`
Remove the old \`CET = timezone(timedelta(hours=1))\` line.

## STEP 3: Replace hardcoded ZoneInfo('Europe/Warsaw') (4 files)
These already use ZoneInfo correctly but should import from central config:

1. app/analysis/relationship/health_scorer.py — \`CET = ZoneInfo('Europe/Warsaw')\`
   → \`from app.config.timezone import APP_TIMEZONE as CET\`

2. app/ingestion/whatsapp_live/wa_repair_monitor.py — \`ZoneInfo('Europe/Warsaw')\`
   → \`from app.config.timezone import APP_TIMEZONE\`

3. app/orchestrator/calendar_manager.py — \`WAR = ZoneInfo('Europe/Warsaw')\`
   → \`from app.config.timezone import APP_TIMEZONE as WAR, APP_TIMEZONE_NAME\`
   Also replace \`'Europe/Warsaw'\` strings in Graph API payloads with APP_TIMEZONE_NAME

4. scripts/check_api_credits.py — \`CET = zoneinfo.ZoneInfo('Europe/Warsaw')\`
   → \`from app.config.timezone import APP_TIMEZONE as CET\`

## STEP 4: Replace datetime.now(timezone.utc) ONLY in display/response code
⚠️ CRITICAL: Only change timestamps in API responses and display strings — NEVER change values bound to DB inserts.
Double-offset bug risk: if you change \`cur.execute(..., (datetime.now(tz=utc), ...))\` to CET,
data will be stored as CET but interpreted as UTC by PostgreSQL, causing 1-2h drift.

DISPLAY/RESPONSE CODE ONLY (where result is returned to user):
1. app/api/decisions.py — variables \`decided_at\` and \`outcome_date\` ONLY in API response dicts (NOT in cur.execute)
2. app/api/voice_ws.py — \`"timestamp":\` fields in WebSocket message dicts sent to users
3. app/api/ingestion_dashboard.py — \`"generated_at":\` in API response payloads
4. app/omnius/bridge.py — \`"generated_at":\` in response dict payloads (NOT bound to INSERT)
5. scripts/non_regression_gate.py — string formatting for console output

NEVER change datetime.now(tz=timezone.utc) when it is:
- Passed to \`cur.execute(..., params)\`
- Part of an INSERT/UPDATE statement
- Bound to a TIMESTAMPTZ column
- In low-level DB/ingestion modules (use PostgreSQL NOW() instead)
- In time.time() calls (performance counters)

For safe changes: import \`from app.config.timezone import now as tz_now\` and replace
\`datetime.now(tz=timezone.utc)\` with \`tz_now()\` ONLY in assignment statements where the result
is immediately added to a response dict or formatting string.

## STEP 5: Update cron_registry.py to use central config
File: app/orchestrator/cron_registry.py line 229
Replace hardcoded \`TZ=Europe/Warsaw\` with import from config:

\`\`\`python
from app.config.timezone import APP_TIMEZONE_NAME
# In generate_crontab():
lines = [f'TZ={APP_TIMEZONE_NAME}', ...]
\`\`\`

## STEP 6: Update SQL AT TIME ZONE references
File: app/analysis/wellbeing_monitor.py line 106
Replace \`AT TIME ZONE 'Europe/Warsaw'\` with parameterized:

\`\`\`python
from app.config.timezone import APP_TIMEZONE_NAME
# In SQL: AT TIME ZONE %s  with param APP_TIMEZONE_NAME
\`\`\`

Same for app/orchestrator/task_monitor.py and delegation_chain.py where
\`AT TIME ZONE 'UTC'\` is used.

## STEP 7: Verify
1. Run: python -c 'from app.config.timezone import APP_TIMEZONE, now, today; print(now(), today())'
2. Run: grep -rn \"ZoneInfo.*Europe/Warsaw\" app/ scripts/ --include='*.py' | grep -v config/timezone | grep -v __pycache__
   (should return ZERO results — all centralized)
3. Run: grep -rn \"timezone(timedelta(hours=1))\" app/ --include='*.py'
   (should return ZERO results — no broken CET)
4. Run: ruff check app/config/timezone.py app/analysis/relationship/ app/orchestrator/calendar_manager.py app/orchestrator/cron_registry.py

## STEP 8: Commit
git add app/config/timezone.py app/analysis/relationship/ app/orchestrator/calendar_manager.py app/orchestrator/cron_registry.py app/analysis/wellbeing_monitor.py
git commit -m 'refactor(timezone): centralize all timezone handling to app/config/timezone.py

Single source of truth: APP_TIMEZONE = Europe/Warsaw (CET/CEST).
- Created app/config/timezone.py with now(), today(), to_app_tz()
- Replaced 3x broken CET=timezone(timedelta(hours=1)) — no DST support
- Replaced 4x hardcoded ZoneInfo(Europe/Warsaw)
- Updated cron_registry, calendar_manager, wellbeing_monitor
- User-facing timestamps now use CET instead of UTC'

## RULES
- Read each file BEFORE editing
- Do NOT change PostgreSQL NOW() or internal DB timestamps
- Do NOT change time.time() performance timers
- Do NOT change frontend code (browser handles timezone via locale)
- All SQL must remain parameterized
- Use structlog, not print()
- Verify imports work after changes
" 2>&1 | tee -a "$LOG"
CLAUDE_RC=${PIPESTATUS[0]}

log "Exit code: $CLAUDE_RC"

# Post-flight
if [[ ${CLAUDE_RC:-1} -eq 0 ]]; then
	log "Post-flight verification..."
	.venv/bin/python -c "from app.config.timezone import APP_TIMEZONE, now, today; print('TZ:', APP_TIMEZONE, 'Now:', now(), 'Today:', today())" 2>&1 | tee -a "$LOG"

	remaining=$(grep -rn "ZoneInfo.*Europe/Warsaw" app/ scripts/ --include='*.py' 2>/dev/null | grep -v config/timezone | grep -v __pycache__ | wc -l)
	log "Remaining hardcoded ZoneInfo('Europe/Warsaw'): $remaining"

	broken_cet=$(grep -rn "timezone(timedelta(hours=1))" app/ --include='*.py' 2>/dev/null | wc -l)
	log "Remaining broken CET (no DST): $broken_cet"

	log "=== Timezone Centralization — done ==="
else
	log "SKIPPING post-flight — claude exited non-zero"
fi
