# G08: Ingestion health dashboard + metrics + cron registration

## TASK

### 1. Wypełnij tabelę `ingestion_health`
Dodaj UNIQUE constraint jeśli brak:
```sql
ALTER TABLE ingestion_health ADD CONSTRAINT uq_ih_date_source UNIQUE (check_date, source_type);
```

Data Guardian (G04) już pisze do niej — tutaj dodaj:
- Dane historyczne (backfill z sources/documents tabeli)
- 7-day rolling average
- Trend indicator (growing/stable/declining)

### 2. API endpoint: `GET /ingestion/dashboard`
Zwraca:
```json
{
  "sources": [
    {
      "source_type": "email",
      "status": "critical",
      "last_import": "2026-03-24T21:02:09Z",
      "hours_stale": 120,
      "sla_hours": 2,
      "docs_24h": 0,
      "docs_7d_avg": 45.2,
      "trend": "declining",
      "circuit_breaker": "closed",
      "dlq_pending": 3,
      "last_error": "UniqueViolation..."
    }
  ],
  "extraction": {
    "entity_backlog": 1304,
    "event_backlog": 1304,
    "embedding_backlog": 0,
    "workers_running": 0
  },
  "alerts": {
    "unacknowledged_critical": 2,
    "recent_auto_fixes": 5
  },
  "overall_health": "critical"  // ok / warning / critical
}
```

### 3. Zarejestruj WSZYSTKIE guardian crony
Dodaj do crontab:
```
# Data Guardian (co 15 min)
*/15 * * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.guardian.data_guardian >> logs/data_guardian.log 2>&1
# Extraction Watchdog (co 30 min)
*/30 * * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.guardian.extraction_watchdog >> logs/extraction_watchdog.log 2>&1
# DLQ Worker (co 2h)
15 */2 * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.guardian.dlq_worker >> logs/dlq.log 2>&1
# Token Refresh (co 30 min)
*/30 * * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.ingestion.graph_api.auth --refresh-proactive >> logs/graph_auth.log 2>&1
# Critical Alert Repeat (co 2h)
0 */2 * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -c "from app.guardian.alert_manager import AlertManager; AlertManager().repeat_unacknowledged()" >> logs/alerts.log 2>&1
```

### 4. MCP tool: `gilbertus_data_health`
Dodaj do MCP server:
```python
@server.tool(name="gilbertus_data_health")
async def data_health(action: str = "dashboard"):
    """Check data pipeline health. Actions: dashboard, sources, dlq, alerts, fix"""
```

## WAŻNE
- Dashboard endpoint nie wymaga auth (jest na localhost)
- Overall health = worst source status
- Trend = compare docs_24h vs docs_7d_avg
