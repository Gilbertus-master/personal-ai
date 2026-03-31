# Gilbertus Webapp Audit Report
Date: 2026-03-31 14:27:19
WSL IP: 172.17.44.2
API: http://172.17.44.2:8000
Frontend: http://172.17.44.2:3000

## API Endpoints

/status → 200
/brief/today → 200
/alerts → 200
/timeline → 405
/admin/roles → 200
/autofixers/dashboard → 200
/code-fixes/manual-queue → 200
/crons → 500
/crons/summary → 200
/costs/budget → 200
/people → 200
/commitments → 200
/compliance/dashboard → 200
/market/dashboard → 200
/process-intel?action=dashboard → 404
/calendar/week → 404

## Frontend Pages

/dashboard → 200
/brief → 200
/chat → 200
/people → 200
/intelligence → 200
/compliance → 200
/market → 200
/finance → 200
/process → 200
/decisions → 200
/calendar → 200
/documents → 200
/voice → 200
/admin → 200
/admin/crons → 200
/admin/status → 200
/admin/costs → 200
/admin/code-review → 200
/admin/autofixers → 200
/admin/roles → 200
/admin/users → 200
/admin/audit → 200
/settings → 200

## CORS
access-control-allow-origin: *

## JS API URL
http://172.17.44.2:8000

## Session
{}

## Next.js Errors
/home/sebastian/personal-ai/frontend/apps/web/.next/dev/logs/next-development.log
