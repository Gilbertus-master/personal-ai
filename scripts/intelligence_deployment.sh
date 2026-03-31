#!/usr/bin/env bash
# Intelligence Deployment Orchestrator
# Deploys People & Business intelligence crons + Gilbertus App pages
set -uo pipefail

PROJ=/home/sebastian/personal-ai
LOG="$PROJ/logs/intelligence_deployment.log"
CLAUDE_BIN="${CLAUDE_BIN:-/home/sebastian/.npm-global/bin/claude}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }
mkdir -p "$PROJ/logs"

log "=== Intelligence Deployment — start ==="
cd "$PROJ"

# Collect current state
CURRENT_CRONS=$(crontab -l 2>/dev/null | grep -c -v "^#\|^$" || true)
log "Current crons: $CURRENT_CRONS"

$CLAUDE_BIN --permission-mode bypassPermissions --print --max-turns 80 \
"You are deploying People & Business intelligence features to the Gilbertus App.

## CURRENT STATE
- 50+ MCP tools already registered in mcp_gilbertus/server.py
- 87 analysis modules in app/analysis/
- 160+ API endpoints in app/api/main.py
- 57 frontend pages
- $CURRENT_CRONS active cron jobs

## TASK 1: Deploy Daily/Weekly Intelligence Crons

Read app/orchestrator/cron_registry.py to understand the cron system (SEED_JOBS dict).
Add these cron jobs to SEED_JOBS if they don't already exist:

### People Intelligence (daily/weekly):
1. **sentiment_daily** — Daily 21:00 CET, runs sentiment analysis for top 20 contacts
   Command: .venv/bin/python -m app.analysis.sentiment_tracker --top 20

2. **commitment_check** — Every 2h during work hours (8-20), check for overdue commitments
   Command: .venv/bin/python -m app.analysis.commitment_tracker
   (verify this module exists and has __main__ block)

3. **delegation_analysis** — Weekly Monday 7:00 CET, delegation effectiveness report
   Command: .venv/bin/python -c \"from app.analysis.delegation_tracker import run_analysis; run_analysis()\"
   (verify module exists)

4. **network_analysis** — Weekly Sunday 19:00 CET, communication network/silo detection
   Command: .venv/bin/python -c \"from app.analysis.network_graph import run_analysis; run_analysis()\"
   (verify module exists)

5. **response_tracking** — Daily 20:00 CET, track response times by person/channel
   Command: .venv/bin/python -c \"from app.analysis.response_tracker import run_tracking; run_tracking()\"

6. **blind_spot_scan** — Weekly Wednesday 18:00 CET, detect blind spots
   Command: .venv/bin/python -m app.analysis.blind_spot_detector
   (verify module exists)

### Business Intelligence (daily/weekly):
7. **opportunity_scan** — Every 4h (already exists as every 2h — verify and keep)

8. **org_health_daily** — Daily 6:00 CET, org health score
   Command: .venv/bin/python -c \"from app.analysis.org_health import calculate_org_health; print(calculate_org_health())\"

9. **correlation_scan** — Daily 22:00 CET, cross-domain pattern detection
   Command: .venv/bin/python -c \"from app.analysis.correlation import run_correlation_scan; run_correlation_scan()\"
   (verify module exists)

10. **strategic_goals_update** — Weekly Monday 6:00 CET, update goal progress
    Command: .venv/bin/python -c \"from app.analysis.strategic_goals import update_goals; update_goals()\"

11. **decision_enrichment** — Daily 23:00 CET, enrich today's decisions with outcomes
    Command: .venv/bin/python -m app.analysis.decision_enrichment

12. **process_discovery** — Weekly Sunday 17:00 CET (verify if already exists)

13. **data_flow_validation** — Daily 4:00 CET, validate data flows
    Command: .venv/bin/python -c \"from app.analysis.data_flow_mapper import validate_flows; validate_flows()\"

### IMPORTANT for each cron:
- VERIFY the module/function EXISTS before adding
- If module doesn't have the expected function, SKIP it (don't create new modules)
- Use the pattern from existing SEED_JOBS
- Schedule format uses Europe/Warsaw (TZ is set in crontab header)
- All commands must have cd /home/sebastian/personal-ai && prefix
- Log to logs/{job_name}.log

After adding to SEED_JOBS, regenerate crontab:
.venv/bin/python -c \"from app.orchestrator.cron_registry import sync_crontab; sync_crontab('sebastian')\"

## TASK 2: Add Intelligence Hub pages to Gilbertus App

### 2A: People Intelligence page at /people/intelligence
Create: frontend/apps/web/app/(app)/people/intelligence/page.tsx

This page shows a dashboard with:
- Sentiment trends for top contacts (last 30 days)
- Open/overdue commitments summary
- Delegation effectiveness scores
- Response time stats
- Network analysis (silos, bottlenecks)

Read existing patterns:
- frontend/apps/web/app/(app)/intelligence/page.tsx (reference page)
- frontend/apps/web/lib/hooks/use-dashboard.ts (hook pattern)
- frontend/packages/api-client/src/dashboard.ts (API client pattern)

For data, use existing API endpoints:
- GET /sentiment?person=all&weeks=4
- GET /commitments?status=open
- GET /delegation/stats
- GET /people (for contact list)
Check which endpoints actually exist by reading app/api/main.py

Create a simple hook useIntelligenceHub() that fetches from available endpoints.
Create a component IntelligenceHub in packages/ui/src/components/intelligence/

### 2B: Business Intelligence page at /intelligence/business
Create: frontend/apps/web/app/(app)/intelligence/business/page.tsx

Dashboard with:
- Top opportunities by ROI
- Org health score (gauge)
- Recent correlations found
- Process inefficiencies
- Decision patterns

Use existing endpoints:
- GET /opportunities?status=new&limit=10
- GET /org-health/score
- GET /correlations/recent
- GET /process-intel?action=dashboard
- GET /decisions/patterns

### 2C: Add navigation links
Add sub-navigation or links from existing /people and /intelligence pages to the new sub-pages.

## TASK 3: Verify everything works

1. Check crontab was updated:
   crontab -l | grep -c -v '^#\|^$'
   (should be more than $CURRENT_CRONS)

2. Verify new pages load:
   curl -s -o /dev/null -w '%{http_code}' http://172.17.44.2:3000/people/intelligence
   curl -s -o /dev/null -w '%{http_code}' http://172.17.44.2:3000/intelligence/business

3. Verify API endpoints exist:
   curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/sentiment
   curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/opportunities
   curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/org-health/score

4. Test one analysis module manually:
   .venv/bin/python -c 'from app.analysis.org_health import calculate_org_health; print(calculate_org_health())'

5. Commit all changes:
   git add -A
   git commit -m 'feat(intelligence): deploy People & Business daily crons + App pages

   - Added 10+ intelligence cron jobs (sentiment, commitments, delegation,
     network, blind spots, org health, correlation, goals, decisions)
   - New /people/intelligence page with contact analytics dashboard
   - New /intelligence/business page with ROI opportunities and org health
   - All crons verified against existing modules'

## RULES
- Do NOT create new Python analysis modules — only schedule EXISTING ones
- Verify each module/function exists before adding cron
- All SQL must be parameterized
- Use structlog, not print()
- Frontend: follow existing patterns (CSS variables, Tailwind, TanStack Query)
- Use app.config.timezone for any datetime operations
" 2>&1 | tee -a "$LOG"

log "Exit code: $?"

# Post-deployment check
log "Post-deployment verification..."
NEW_CRONS=$(crontab -l 2>/dev/null | grep -c -v "^#\|^$" || true)
log "Crons: $CURRENT_CRONS → $NEW_CRONS"

for page in "/people/intelligence" "/intelligence/business"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "http://172.17.44.2:3000${page}" 2>/dev/null || true)
  log "Page $page → $code"
done

log "=== Intelligence Deployment — done ==="
