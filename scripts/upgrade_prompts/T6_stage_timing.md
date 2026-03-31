# TASK T6: Per-Stage Timing → PostgreSQL
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T6.done

## Context
The `StageTimer` class exists in `app/db/stage_timer.py` and is used in the `/ask` endpoint.
However, timing data is never persisted - it's only used locally per request.
We need to save timing data to PG so we can: (a) see performance trends, (b) power T15 retrieval alerts.

The `/ask` endpoint in `app/api/main.py` already uses `timer = StageTimer()` and calls `timer.start()/end()`.
After the request, meta dict includes timing data. We need to capture it.

## What to do

### Step 1: Create the database table

Run this SQL:
```sql
CREATE TABLE IF NOT EXISTS query_stage_times (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_id TEXT,
    question_type TEXT,
    analysis_depth TEXT,
    used_fallback BOOLEAN DEFAULT FALSE,
    retrieved_count INTEGER,
    total_ms INTEGER,
    interpret_ms INTEGER,
    retrieve_ms INTEGER,
    answer_ms INTEGER,
    channel TEXT,
    model_used TEXT
);

CREATE INDEX IF NOT EXISTS idx_qst_created_at ON query_stage_times (created_at);
CREATE INDEX IF NOT EXISTS idx_qst_question_type ON query_stage_times (question_type);
```

Run via:
```
docker exec gilbertus-postgres psql -U gilbertus -c "CREATE TABLE IF NOT EXISTS query_stage_times (id BIGSERIAL PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), request_id TEXT, question_type TEXT, analysis_depth TEXT, used_fallback BOOLEAN DEFAULT FALSE, retrieved_count INTEGER, total_ms INTEGER, interpret_ms INTEGER, retrieve_ms INTEGER, answer_ms INTEGER, channel TEXT, model_used TEXT); CREATE INDEX IF NOT EXISTS idx_qst_created_at ON query_stage_times (created_at);"
```

### Step 2: Create persistence helper

Create `app/db/timing_persistence.py`:

```python
"""Persist per-request stage timing data to PostgreSQL."""
from __future__ import annotations
import structlog
from app.db.postgres import get_pg_connection

log = structlog.get_logger("timing_persistence")

def save_timing(
    *,
    request_id: str | None = None,
    question_type: str | None = None,
    analysis_depth: str | None = None,
    used_fallback: bool = False,
    retrieved_count: int | None = None,
    total_ms: int | None = None,
    interpret_ms: int | None = None,
    retrieve_ms: int | None = None,
    answer_ms: int | None = None,
    channel: str | None = None,
    model_used: str | None = None,
) -> None:
    """Save timing data. Non-blocking - errors are swallowed."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO query_stage_times
                    (request_id, question_type, analysis_depth, used_fallback,
                     retrieved_count, total_ms, interpret_ms, retrieve_ms,
                     answer_ms, channel, model_used)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    request_id, question_type, analysis_depth, used_fallback,
                    retrieved_count, total_ms, interpret_ms, retrieve_ms,
                    answer_ms, channel, model_used
                ))
            conn.commit()
    except Exception as e:
        log.warning("timing_persistence.failed", error=str(e))
```

### Step 3: Add performance stats endpoint to main.py

Find a good place near other status endpoints in `app/api/main.py` and add:

```python
@app.get("/performance/stats")
def performance_stats(days: int = 7):
    """Per-stage timing statistics for the last N days."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        question_type,
                        COUNT(*) as request_count,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_ms)) as p50_total,
                        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_ms)) as p95_total,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY interpret_ms)) as p50_interpret,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY retrieve_ms)) as p50_retrieve,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY answer_ms)) as p50_answer,
                        ROUND(AVG(retrieved_count::float), 1) as avg_chunks,
                        ROUND(AVG(CASE WHEN used_fallback THEN 1.0 ELSE 0.0 END) * 100, 1) as fallback_pct
                    FROM query_stage_times
                    WHERE created_at > NOW() - (%(days)s || ' days')::interval
                    GROUP BY question_type
                    ORDER BY request_count DESC
                """, {"days": days})
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return {"days": days, "by_question_type": rows}
    except Exception as e:
        return {"error": str(e)}
```

### Step 4: Wire save_timing into /ask endpoint

In `app/api/main.py`, find the section AFTER the response is built (near `_save_answer_cache` call) and add timing persistence. Look for where `response_meta` is populated and add:

```python
# Near end of /ask handler, after response_meta is built:
try:
    from app.db.timing_persistence import save_timing
    _timer_data = timer.summary() if hasattr(timer, 'summary') else {}
    save_timing(
        question_type=interpreted.question_type,
        analysis_depth=interpreted.analysis_depth,
        used_fallback=getattr(interpreted, 'used_fallback', False) or response_meta.get('used_fallback', False),
        retrieved_count=len(redacted_matches_for_answer) if 'redacted_matches_for_answer' in dir() else None,
        total_ms=int((time.time() - started_at) * 1000),
        interpret_ms=_timer_data.get('interpret'),
        retrieve_ms=_timer_data.get('retrieve'),
        answer_ms=_timer_data.get('answer'),
        channel=ask_req.channel,
        model_used=response_meta.get('model_used'),
    )
except Exception:
    pass  # timing is non-critical
```

First, check what methods StageTimer has:
```
cat /home/sebastian/personal-ai/app/db/stage_timer.py
```

Then add the timing data accordingly (adapt to actual StageTimer API).

### Step 5: Restart and verify

```
systemctl --user restart gilbertus-api
sleep 5
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query": "test timing", "answer_length": "short"}'
sleep 2
docker exec gilbertus-postgres psql -U gilbertus -c "SELECT * FROM query_stage_times ORDER BY created_at DESC LIMIT 3;"
curl -s http://127.0.0.1:8000/performance/stats | python3 -m json.tool
```

## Completion
```
echo "done" > /tmp/gilbertus_upgrade/status/T6.done
openclaw system event --text "Upgrade T6 done: per-stage timing persisted to PG" --mode now
```
