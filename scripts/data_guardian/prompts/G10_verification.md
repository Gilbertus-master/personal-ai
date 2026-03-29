# G10: End-to-end verification + non-regression + final cron setup

## TASK

### 1. Verify ALL fixes from G01-G09
Run each check:

```bash
# G01: insert_source upsert works
.venv/bin/python3 -c "
from app.ingestion.common.db import insert_source
from app.db.postgres import get_pg_connection
with get_pg_connection() as conn:
    s1 = insert_source(conn, 'test_verify', 'test')
    s2 = insert_source(conn, 'test_verify', 'test')
    assert s1 == s2, f'UPSERT BROKEN: {s1} != {s2}'
    with conn.cursor() as cur:
        cur.execute(\"DELETE FROM sources WHERE source_type='test_verify'\")
    conn.commit()
print('G01 OK: insert_source upsert works')
"

# G02: Graph API token valid
.venv/bin/python3 -c "
from app.ingestion.graph_api.auth import get_token_status
status = get_token_status()
print(f'G02: Token status = {status}')
"

# G03: Circuit breakers initialized
.venv/bin/python3 -c "
from app.core.resilience import BREAKERS
for name, b in BREAKERS.items():
    print(f'G03: {name} = {b.state}')
"

# G04: Data Guardian runs without error
.venv/bin/python3 -m app.guardian.data_guardian --dry-run 2>&1 | tail -5

# G05: DLQ table exists
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT COUNT(*) FROM ingestion_dlq;"

# G06: Extraction watchdog runs
.venv/bin/python3 -m app.guardian.extraction_watchdog --dry-run 2>&1 | tail -5

# G07: Alert manager works
.venv/bin/python3 -c "
from app.guardian.alert_manager import AlertManager
am = AlertManager()
print(f'G07: AlertManager initialized, dedup_window={am.dedup_window}s')
"

# G08: Dashboard endpoint works
curl -s http://127.0.0.1:8000/ingestion/dashboard | python3 -m json.tool | head -20

# G09: Quality checks run
.venv/bin/python3 -m app.guardian.quality_checks --dry-run 2>&1 | tail -5
```

### 2. End-to-end data flow test
```bash
# Trigger email sync
.venv/bin/python3 -m app.ingestion.graph_api.email_sync --inbox --limit 5 2>&1 | tail -10

# Check new documents appeared
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT source_type, COUNT(*) FROM documents WHERE created_at > NOW() - INTERVAL '1 hour' GROUP BY source_type;"

# Check embedding pipeline
.venv/bin/python3 -m app.retrieval.index_chunks --batch-size 10 --limit 10 2>&1 | tail -5

# Check source freshness
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT source_type, MAX(imported_at) as last, EXTRACT(EPOCH FROM NOW()-MAX(imported_at))/3600 as hours_ago FROM sources GROUP BY source_type ORDER BY hours_ago;"
```

### 3. Verify crontab completeness
```bash
crontab -l | grep -c "guardian\|dlq\|watchdog\|graph_auth\|alert"
# Should be >= 5 new guardian crons
```

### 4. Update CLAUDE.md
Add to CLAUDE.md:
- Data Guardian section: what it does, how it works
- New cron jobs: guardian, watchdog, dlq, token refresh, alert repeat
- New API endpoints: /ingestion/dashboard, /dlq, /alerts/{id}/acknowledge
- New MCP tool: gilbertus_data_health
- New tables: ingestion_dlq, guardian_alerts

### 5. Update non-regression monitor
Add Data Guardian checks to `scripts/non_regression_monitor.sh`:
- guardian cron running
- ingestion_health table not empty
- DLQ not growing
- No unacknowledged critical alerts > 6h

### 6. Final status check
```bash
echo "=== DATA GUARDIAN STATUS ==="
curl -s http://127.0.0.1:8000/ingestion/dashboard | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Overall: {d[\"overall_health\"]}')
for s in d['sources']:
    print(f'  {s[\"source_type\"]:20} {s[\"status\"]:10} {s[\"hours_stale\"]:.1f}h stale (SLA: {s[\"sla_hours\"]}h)')
print(f'Extraction backlog: {d[\"extraction\"][\"entity_backlog\"]} entities, {d[\"extraction\"][\"event_backlog\"]} events')
print(f'Alerts: {d[\"alerts\"][\"unacknowledged_critical\"]} critical unacked')
"
```

## ACCEPTANCE CRITERIA
- [ ] ALL sources importing (no crashes)
- [ ] Email/Teams freshness < 2h
- [ ] Zero UniqueViolation errors in logs
- [ ] Circuit breakers all CLOSED
- [ ] DLQ has 0 pending items (or all retried)
- [ ] Guardian crons registered and running
- [ ] Dashboard endpoint returns valid JSON
- [ ] Quality score > 80
- [ ] No unacknowledged critical alerts
