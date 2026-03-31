#!/usr/bin/env bash
# Autofixer Dashboard Orchestrator — builds the Autofixers tab in Gilbertus App
set -euo pipefail

PROJ=/home/sebastian/personal-ai
LOG="$PROJ/logs/autofixer_dashboard_build.log"
CLAUDE_BIN="${CLAUDE_BIN:-/home/sebastian/.npm-global/bin/claude}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }
mkdir -p "$PROJ/logs"

# Concurrency guard — prevent simultaneous runs
LOCKFILE="$PROJ/logs/autofixer_dashboard_build.lock"
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  log "Another instance is running (lockfile held). Exiting."
  exit 0
fi
trap 'flock -u 9; rm -f "$LOCKFILE"' EXIT INT TERM

log "=== Autofixer Dashboard Build — start ==="
cd "$PROJ"

set +e
timeout 1800 $CLAUDE_BIN --dangerously-skip-permissions --print --max-turns 50 \
  "Read scripts/autofixer_dashboard_prompt.md for the full specification.

PHASE 1 — PLAN: Before writing any code, read these reference files to understand patterns:
- frontend/packages/api-client/src/admin.ts
- frontend/packages/api-client/src/index.ts
- frontend/apps/web/lib/hooks/use-admin.ts
- frontend/packages/rbac/src/navigation.ts
- frontend/packages/ui/src/components/admin/code-review-queue.tsx
- frontend/packages/ui/src/index.ts
- app/api/main.py (search for /code-fixes/manual-queue endpoint as reference)

PHASE 2 — IMPLEMENT all 6 steps from the prompt:
1. Backend API: GET /autofixers/dashboard in app/api/main.py
2. API client types + function in frontend/packages/api-client/src/admin.ts + index.ts
3. React hook useAutofixerDashboard() in frontend/apps/web/lib/hooks/use-admin.ts
4. UI component frontend/packages/ui/src/components/admin/autofixer-dashboard.tsx + export from index.ts
5. Page route frontend/apps/web/app/(app)/admin/autofixers/page.tsx
6. Navigation: add to rbac navigation.ts + Wrench icon to sidebar.tsx ICON_MAP

PHASE 3 — VERIFY:
- Run: cd frontend && pnpm typecheck 2>&1 | tail -30
- Fix any TypeScript errors
- Commit: git add app/api/main.py frontend/packages/api-client/src/admin.ts frontend/packages/api-client/src/index.ts frontend/apps/web/lib/hooks/use-admin.ts frontend/packages/ui/src/components/admin/autofixer-dashboard.tsx frontend/packages/ui/src/index.ts frontend/apps/web/app/\(app\)/admin/autofixers/page.tsx frontend/packages/rbac/src/navigation.ts && git commit -m 'feat(admin): add Autofixers dashboard — dual repair pipeline monitoring'" 2>&1 | tee -a "$LOG"
exit_code=$?
set -e

log "Exit code: $exit_code"

# Post-flight
log "Post-flight verification..."
cd "$PROJ/frontend"
for f in "apps/web/app/(app)/admin/autofixers/page.tsx" "packages/ui/src/components/admin/autofixer-dashboard.tsx"; do
  test -f "$f" && log "✅ $f" || log "❌ $f missing"
done
grep -q "autofixers/dashboard" "$PROJ/app/api/main.py" && log "✅ Backend endpoint" || log "❌ Backend endpoint missing"

log "=== Done ==="
