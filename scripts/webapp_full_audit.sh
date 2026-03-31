#!/usr/bin/env bash
# Gilbertus Webapp Full Audit & Fix Orchestrator
# Tests every page, API endpoint, finds all issues, fixes them
set -uo pipefail

PROJ=/home/sebastian/personal-ai
LOG="$PROJ/logs/webapp_full_audit.log"
CLAUDE_BIN="${CLAUDE_BIN:-/home/sebastian/.npm-global/bin/claude}"
WSL_IP=$(hostname -I | awk '{print $1}')
API="http://${WSL_IP}:8000"
FRONTEND="http://${WSL_IP}:3000"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }
mkdir -p "$PROJ/logs"

log "=== Webapp Full Audit — start ==="
log "WSL_IP=$WSL_IP API=$API FRONTEND=$FRONTEND"

# ── Phase 1: Test all backend API endpoints ─────────────────────────────
log "Phase 1: Testing backend API endpoints..."
API_RESULTS=""
for endpoint in \
  "/status" "/brief/today" "/alerts" "/timeline" "/admin/roles" \
  "/autofixers/dashboard" "/code-fixes/manual-queue" "/crons" "/crons/summary" \
  "/costs/budget" "/people" "/commitments" "/compliance/dashboard" \
  "/market/dashboard" "/process-intel?action=dashboard" "/calendar/week"
do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${API}${endpoint}" 2>/dev/null)
  status="OK"
  [ "$code" != "200" ] && status="FAIL($code)"
  log "  API $endpoint → $status"
  API_RESULTS="${API_RESULTS}\n${endpoint} → ${code}"
done

# ── Phase 2: Test all frontend pages ────────────────────────────────────
log "Phase 2: Testing frontend pages..."
PAGE_RESULTS=""
for page in \
  "/dashboard" "/brief" "/chat" "/people" "/intelligence" "/compliance" \
  "/market" "/finance" "/process" "/decisions" "/calendar" "/documents" \
  "/voice" "/admin" "/admin/crons" "/admin/status" "/admin/costs" \
  "/admin/code-review" "/admin/autofixers" "/admin/roles" "/admin/users" \
  "/admin/audit" "/settings"
do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "${FRONTEND}${page}" 2>/dev/null)
  status="OK"
  [ "$code" != "200" ] && status="FAIL($code)"
  log "  PAGE $page → $status"
  PAGE_RESULTS="${PAGE_RESULTS}\n${page} → ${code}"
done

# ── Phase 3: Test CORS from frontend origin ─────────────────────────────
log "Phase 3: Testing CORS..."
cors_header=$(curl -s -I -H "Origin: ${FRONTEND}" "${API}/status" 2>/dev/null | grep -i "access-control-allow-origin" | tr -d '\r')
log "  CORS header: $cors_header"

# ── Phase 4: Test that frontend JS has correct API URL ──────────────────
log "Phase 4: Checking frontend API URL in JS bundle..."
js_api_url=$(curl -s "${FRONTEND}/dashboard" 2>/dev/null | grep -oP 'src="/_next/[^"]*\.js"' | head -20 | while read -r src; do
  url="${FRONTEND}$(echo $src | grep -oP '/_next/[^"]*')"
  match=$(curl -s "$url" 2>/dev/null | grep -oE 'http://[0-9.]+:8000|window\.location\.hostname' | head -1)
  if [ -n "$match" ]; then echo "$match"; break; fi
done)
log "  JS API URL pattern: $js_api_url"

# ── Phase 5: Check Next.js dev server logs for errors ──────────────────
log "Phase 5: Checking Next.js error logs..."
nextjs_errors=$(find "$PROJ/frontend/apps/web/.next/dev/logs/" -name "*.log" -exec grep -l "error\|Error\|ERROR" {} \; 2>/dev/null | head -5)
if [ -n "$nextjs_errors" ]; then
  for f in $nextjs_errors; do
    log "  Error in: $f"
    tail -5 "$f" | while read -r line; do log "    $line"; done
  done
fi

# ── Phase 6: Check auth/session ─────────────────────────────────────────
log "Phase 6: Testing auth session..."
session=$(curl -s "${FRONTEND}/api/auth/session" 2>/dev/null)
log "  Session response: $session"

# ── Phase 7: Test actual data fetching (simulating browser) ─────────────
log "Phase 7: Simulating browser data fetch..."
for api_path in "/status" "/brief/today" "/alerts" "/admin/roles"; do
  response=$(curl -s --max-time 10 \
    -H "Origin: ${FRONTEND}" \
    -H "Referer: ${FRONTEND}/dashboard" \
    -H "Accept: application/json" \
    "${API}${api_path}" 2>/dev/null | head -c 200)
  has_data="NO"
  [ -n "$response" ] && [ "$response" != "null" ] && [ "$response" != "{}" ] && has_data="YES"
  log "  Browser fetch ${api_path} → data=$has_data"
done

# ── Phase 8: Write diagnostic report ───────────────────────────────────
REPORT="$PROJ/logs/webapp_audit_report.md"
cat > "$REPORT" << REPORT_EOF
# Gilbertus Webapp Audit Report
Date: $(date '+%Y-%m-%d %H:%M:%S')
WSL IP: $WSL_IP
API: $API
Frontend: $FRONTEND

## API Endpoints
$(echo -e "$API_RESULTS")

## Frontend Pages
$(echo -e "$PAGE_RESULTS")

## CORS
$cors_header

## JS API URL
$js_api_url

## Session
$session

## Next.js Errors
$(echo "$nextjs_errors")
REPORT_EOF

log "Phase 8: Report written to $REPORT"

# ── Phase 9: Claude orchestrator fixes ──────────────────────────────────
log "Phase 9: Launching Claude fix orchestrator..."

cd "$PROJ"
$CLAUDE_BIN --permission-mode bypassPermissions --print --max-turns 60 \
  "You are a senior frontend engineer debugging and fixing the Gilbertus webapp.

## Current situation
The webapp at ${FRONTEND} loads HTML but NO DATA appears (loading spinners, empty sections, no KPIs).
Backend API at ${API} works perfectly (confirmed via curl).

## Diagnostic report
$(cat "$REPORT")

## Your task
1. READ the diagnostic report above carefully
2. READ these files to understand the data flow:
   - frontend/packages/api-client/src/base.ts (API URL resolution)
   - frontend/apps/web/next.config.ts (build config)
   - frontend/apps/web/lib/auth.ts (auth config)
   - frontend/apps/web/app/api/auth/[...nextauth]/route.ts (session endpoint)
   - frontend/packages/ui/src/components/rbac-gate.tsx (access control)
   - frontend/packages/rbac/src/hooks.ts (role hooks)
   - frontend/apps/web/app/(app)/layout.tsx (app layout)
   - frontend/apps/web/app/(app)/dashboard/page.tsx (dashboard page)
   - frontend/apps/web/lib/hooks/use-dashboard.ts (data hooks)
   - frontend/apps/web/components/providers.tsx (query client setup)
   - app/api/main.py lines 60-74 (CORS config)

3. IDENTIFY every issue that prevents data from loading:
   - Is the API URL correct in the browser JS bundle?
   - Is CORS configured to allow the frontend origin?
   - Does the session/auth block any requests?
   - Does the middleware redirect to /login?
   - Are there TypeScript/runtime errors preventing rendering?
   - Do React Query hooks have correct configuration?

4. FIX every issue found:
   - Edit files directly
   - Verify each fix
   - Test with: curl -s -H 'Origin: ${FRONTEND}' '${API}/status'

5. After fixing, RESTART the dev server:
   - Kill old: pkill -f 'next-server'
   - Clear cache: rm -rf frontend/apps/web/.next
   - Start new: /home/sebastian/.npm-global/bin/pnpm --filter @gilbertus/web dev > /tmp/nextjs.log 2>&1 &
   - Wait 15 seconds
   - Verify: curl -s -o /dev/null -w '%{http_code}' ${FRONTEND}/dashboard

6. VERIFY the fix works:
   - Check JS bundle has window.location.hostname (not 127.0.0.1)
   - Check CORS allows the origin
   - Check session endpoint returns valid data
   - Test all critical pages return 200

7. Commit all changes:
   git add -A
   git commit -m 'fix(webapp): comprehensive data loading fix — auth, CORS, API URL'

## Key constraints
- Do NOT change business logic
- All SQL must be parameterized
- Use structlog, not print()
- Test everything before committing
" 2>&1 | tee -a "$LOG"

log "Claude exit code: $?"

# ── Phase 10: Post-fix verification ─────────────────────────────────────
log "Phase 10: Post-fix verification..."
sleep 5

for page in "/dashboard" "/admin/autofixers" "/admin/roles"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "${FRONTEND}${page}" 2>/dev/null)
  log "  POST-FIX $page → $code"
done

cors_check=$(curl -s -I -H "Origin: ${FRONTEND}" "${API}/status" 2>/dev/null | grep -i "access-control-allow-origin" | tr -d '\r')
log "  POST-FIX CORS: $cors_check"

log "=== Webapp Full Audit — done ==="
