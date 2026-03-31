# TASK T7: Interpretation Cache → Shared PostgreSQL (L2 Cache)
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T7.done

## Context
`app/retrieval/query_interpreter.py` has an in-memory cache `_interp_cache` (dict).
With 4 uvicorn workers, each has its OWN cache. Same query → 4 separate Anthropic API calls.
Fix: add PG as L2 cache. L1 (in-memory, 5 min TTL) stays. L2 (PG, 15 min TTL) is shared.

## What to do

### Step 1: Create PG table
```
docker exec gilbertus-postgres psql -U gilbertus -c "
CREATE TABLE IF NOT EXISTS interpretation_cache (
    query_hash TEXT PRIMARY KEY,
    result_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_interp_cache_expires ON interpretation_cache(expires_at);
"
```

### Step 2: Read current query_interpreter.py
```
cat /home/sebastian/personal-ai/app/retrieval/query_interpreter.py
```
Understand: _cache_key(), _cache_get(), _cache_put(), interpret_query().

### Step 3: Add PG cache functions to query_interpreter.py

Add these functions AFTER the existing in-memory cache functions:

```python
# L2 PG cache (shared across workers)
_PG_CACHE_TTL_SECONDS = int(os.getenv("INTERPRETATION_CACHE_PG_TTL", "900"))  # 15 min

def _pg_cache_get(key: str) -> "InterpretedQuery | None":
    """Check PG for cached interpretation result."""
    try:
        from app.db.postgres import get_pg_connection
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT result_json FROM interpretation_cache WHERE query_hash = %s AND expires_at > NOW()",
                    (key,)
                )
                row = cur.fetchone()
                if row:
                    # Increment hit count (non-blocking)
                    cur.execute("UPDATE interpretation_cache SET hit_count = hit_count + 1 WHERE query_hash = %s", (key,))
                    conn.commit()
                    return InterpretedQuery(**row[0])
    except Exception as e:
        print(f"[query_interpreter] PG cache get failed: {e}")
    return None

def _pg_cache_put(key: str, result: "InterpretedQuery") -> None:
    """Store interpretation result in PG cache."""
    try:
        from app.db.postgres import get_pg_connection
        import json
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO interpretation_cache (query_hash, result_json, expires_at)
                    VALUES (%s, %s, NOW() + INTERVAL '%s seconds')
                    ON CONFLICT (query_hash) DO UPDATE
                    SET result_json = EXCLUDED.result_json,
                        expires_at = EXCLUDED.expires_at,
                        created_at = NOW()
                """, (key, json.dumps(result_dict), _PG_CACHE_TTL_SECONDS))
            conn.commit()
    except Exception as e:
        print(f"[query_interpreter] PG cache put failed: {e}")
```

### Step 4: Update _cache_get to check PG as L2

Modify the existing `_cache_get()` function:

```python
def _cache_get(key: str) -> InterpretedQuery | None:
    # L1: in-memory cache (fast, per-worker)
    entry = _interp_cache.get(key)
    if entry:
        ts, result = entry
        if time.time() - ts <= INTERPRETATION_CACHE_TTL:
            return result
        _interp_cache.pop(key, None)
    
    # L2: PG cache (shared across workers)
    pg_result = _pg_cache_get(key)
    if pg_result is not None:
        # Warm L1 cache
        _interp_cache[key] = (time.time(), pg_result)
        print(f"[query_interpreter] PG cache HIT for: {key[:40]}")
        return pg_result
    
    return None
```

### Step 5: Update _cache_put to also write to PG

Modify the existing `_cache_put()` function to also write to PG:

```python
def _cache_put(key: str, result: InterpretedQuery) -> None:
    # L1: in-memory
    if len(_interp_cache) >= _CACHE_MAX_SIZE:
        oldest_key = min(_interp_cache, key=lambda k: _interp_cache[k][0])
        _interp_cache.pop(oldest_key, None)
    _interp_cache[key] = (time.time(), result)
    
    # L2: PG (non-blocking)
    _pg_cache_put(key, result)
```

### Step 6: Restart and test
```
systemctl --user restart gilbertus-api
sleep 5

# Make same query twice - second should be cache hit
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query": "co wiem o Rochu Baranowskim", "answer_length": "short", "debug": true}' > /dev/null

curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query": "co wiem o Rochu Baranowskim", "answer_length": "short", "debug": true}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('latency:', d.get('meta',{}).get('latency_ms'), 'ms')"

# Check PG cache has entries
docker exec gilbertus-postgres psql -U gilbertus -c "SELECT query_hash, hit_count, expires_at FROM interpretation_cache ORDER BY created_at DESC LIMIT 5;"
```

### Step 7: Commit
```
cd /home/sebastian/personal-ai
git add app/retrieval/query_interpreter.py
git commit -m "feat(cache): add PG L2 cache for query interpreter

- 4 workers now share interpretation results via PG
- L1: in-memory 5min TTL (per-worker, fast)
- L2: PG 15min TTL (shared, survives worker restarts)
- Reduces Anthropic API calls 4x for repeated queries"
```

## Completion
```
echo "done" > /tmp/gilbertus_upgrade/status/T7.done
openclaw system event --text "Upgrade T7 done: interpretation cache shared via PG" --mode now
```
