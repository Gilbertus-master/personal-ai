# G04: Data Guardian daemon — source freshness SLA monitor + auto-remediation

## CEL
Centralny daemon monitorujący freshness KAŻDEGO źródła danych. Jeśli źródło jest stale → próbuje auto-naprawić. Jeśli nie da rady → eskaluje do człowieka.

## TASK

### Stwórz `/home/sebastian/personal-ai/app/guardian/data_guardian.py`

```python
"""
Data Guardian — self-healing data pipeline monitor.

Runs every 15 minutes. For each data source:
1. Check last import timestamp vs SLA threshold
2. If STALE: diagnose why (log errors, token status, service health)
3. Auto-remediation tier 1: retry import, refresh token, restart service
4. If auto-fix fails: alert human via WhatsApp with diagnosis + fix instructions
5. Log everything to ingestion_health table

SLA Thresholds:
  email:            2 hours (critical business data)
  teams:            2 hours (critical business data)
  calendar:         4 hours
  whatsapp_live:    4 hours
  audio_transcript: 8 hours (Plaud sync less frequent)
  document:         24 hours (manual uploads)
  whatsapp:         24 hours (batch import)
  spreadsheet:      7 days (rarely updated)
  chatgpt:          disabled
"""
```

### Funkcjonalności:

**1. Source Freshness Check**
```sql
SELECT source_type, MAX(imported_at) as last_import,
       EXTRACT(EPOCH FROM NOW() - MAX(imported_at))/3600 as hours_stale
FROM sources GROUP BY source_type;
```
Compare vs SLA thresholds. Status: ok / warning (>50% SLA) / critical (>100% SLA) / dead (>3x SLA).

**2. Diagnosis Engine**
Dla każdego STALE source:
- Sprawdź logi: `tail -20 logs/{source}_sync.log` → szukaj error patterns
- Sprawdź circuit breaker: `BREAKERS[source].state`
- Sprawdź token: Graph API token health
- Sprawdź service: ping Docker containers (postgres, qdrant, whisper)
- Sprawdź cron: czy cron dla tego source jest enabled
- Generuje `diagnosis: str` z root cause

**3. Auto-Remediation (Tier 1 — bez człowieka)**
W zależności od diagnozy:
- "UniqueViolation" → powinno być naprawione (G01), ale restart crona
- "token_expired" → `auth.refresh_token()`, jeśli fail → `auth.client_credentials()`
- "connection_refused" → sprawdź Docker, restart container jeśli dead
- "circuit_breaker_open" → poczekaj na cooldown, loguj
- "timeout" → retry z backoff (G03)
- "worker_stalled" → kill zombie processes, restart
- "service_down" → `docker restart gilbertus-{service}`
- "disk_full" → alert (nie auto-fix — ryzykowne)

**4. Auto-Remediation (Tier 2 — z powiadomieniem)**
Jeśli tier 1 nie pomógł po 2 próbach:
- Wyślij WhatsApp do Sebastiana:
  ```
  🔴 Data Guardian Alert
  Source: {source_type}
  Status: CRITICAL — {hours_stale}h stale (SLA: {sla}h)
  Diagnosis: {diagnosis}
  Auto-fix attempted: {attempts} times, FAILED

  Recommended action:
  {specific_fix_instructions}

  Run: cd /home/sebastian/personal-ai && {fix_command}
  ```
- Fix instructions muszą być KONKRETNE (nie "check the logs" ale "run this command")

**5. Ingestion Health Metrics**
Zapisz do tabeli `ingestion_health`:
```sql
INSERT INTO ingestion_health (check_date, source_type, docs_24h, docs_7d_avg, status, note)
VALUES (CURRENT_DATE, %s, %s, %s, %s, %s)
ON CONFLICT (check_date, source_type) DO UPDATE SET docs_24h=EXCLUDED.docs_24h, ...;
```
(Dodaj UNIQUE constraint na check_date + source_type jeśli nie ma)

**6. Embedding & Extraction Coverage**
Monitoruj:
- Chunks bez embeddings: jeśli > 100 i > 2h → restart index_chunks
- Chunks bez entity extraction: jeśli > 500 i > 4h → restart turbo_extract
- Chunks bez event extraction: analogicznie

### Cron
```
*/15 * * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.guardian.data_guardian >> logs/data_guardian.log 2>&1
```

### Weryfikacja
```bash
# Manual run
.venv/bin/python3 -m app.guardian.data_guardian --verbose

# Check health table
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c "SELECT * FROM ingestion_health ORDER BY check_date DESC LIMIT 20;"
```

## WAŻNE
- NIGDY nie usuwaj danych jako auto-remediation
- NIGDY nie modyfikuj .env jako auto-remediation
- Docker restart TYLKO dla nie-krytycznych kontenerów (whisper OK, postgres NIE)
- Alert dedup: max 1 alert per source per 4 godziny
- Structlog dla WSZYSTKICH logów
- Timeout 30s na każdy health check
