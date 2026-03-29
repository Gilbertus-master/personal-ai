# G05: Dead letter queue + failed import capture + retry

## CEL
Każdy dokument/chunk który FAIL-uje podczas importu trafia do dead letter queue (DLQ) zamiast być stracony. DLQ jest regularnie retried.

## TASK

### 1. Stwórz tabelę DLQ
```sql
CREATE TABLE IF NOT EXISTS ingestion_dlq (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_name TEXT,
    raw_path TEXT,
    title TEXT,
    error_message TEXT NOT NULL,
    error_type TEXT CHECK (error_type IN (
        'parse_error', 'db_error', 'api_error', 'timeout',
        'auth_error', 'format_error', 'size_error', 'unknown'
    )),
    payload JSONB,  -- serialized document data for retry
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'retrying', 'resolved', 'abandoned')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_retry_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_dlq_status ON ingestion_dlq(status) WHERE status IN ('pending', 'retrying');
CREATE INDEX IF NOT EXISTS idx_dlq_source ON ingestion_dlq(source_type);
```

### 2. Wrap import functions z try/except → DLQ
W KAŻDYM imporcie (email, teams, whatsapp, plaud, docs) — owrapuj główną pętlę:
```python
try:
    import_document(...)
except Exception as e:
    insert_into_dlq(source_type, raw_path, title, str(e), payload={...})
    log.warning("import_failed_to_dlq", source=source_type, error=str(e))
```

### 3. DLQ retry worker
Stwórz `app/guardian/dlq_worker.py`:
- Co 2 godziny: pobierz pending items z retry_count < max_retries
- Retry import
- Jeśli sukces → status='resolved'
- Jeśli fail → retry_count++, last_retry_at=NOW()
- Jeśli retry_count >= max_retries → status='abandoned', alert WhatsApp

### 4. DLQ API endpoints
- `GET /dlq` — lista failed imports (status, count per source, oldest)
- `POST /dlq/{id}/retry` — manual retry
- `POST /dlq/retry-all` — retry all pending
- `GET /dlq/stats` — summary per source_type

### 5. Cron
```
15 */2 * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.guardian.dlq_worker >> logs/dlq.log 2>&1
```

## Pliki do modyfikacji
- Nowy: `app/guardian/dlq_worker.py`
- Modify: `app/ingestion/common/db.py` (dodaj insert_into_dlq)
- Modify: Każdy importer (email, teams, whatsapp, plaud, docs) — wrap w try/except
- Modify: `app/api/main.py` — dodaj DLQ endpoints

## WAŻNE
- Payload w JSONB musi zawierać WSZYSTKO potrzebne do retry (tekst, metadane, source info)
- NIE przechowuj binarnych plików w payload (tylko ścieżki)
- Abandoned items → alert z listą (max 1x dziennie)
