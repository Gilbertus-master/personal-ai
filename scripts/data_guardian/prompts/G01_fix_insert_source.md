# G01: Fix insert_source upsert — unblock ALL pipelines

## PROBLEM KRYTYCZNY
`insert_source()` w `/home/sebastian/personal-ai/app/ingestion/common/db.py` NIE ma upsert/get-or-create.
Każde wywołanie robi blind INSERT, co powoduje UniqueViolation crash na `uq_sources_type_name`.

**EFEKT:** WSZYSTKIE pipeline'y danych crashują co 5-15 minut. Email, Teams, WhatsApp, Plaud, Calendar — NIC nie działa od godzin.

## TASK
1. Przeczytaj `/home/sebastian/personal-ai/app/ingestion/common/db.py` — cały plik
2. Znajdź funkcję `insert_source()` — linia ~25
3. Zmień ją na `get_or_create_source()` z wzorcem:
```python
def insert_source(conn, source_type: str, source_name: str) -> int:
    """Get existing source or create new one. Returns source_id."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO sources (source_type, source_name, imported_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (source_type, source_name)
            DO UPDATE SET imported_at = NOW()
            RETURNING id
        """, (source_type, source_name))
        row = cur.fetchone()
        conn.commit()
        return row[0]
```

4. Znajdź WSZYSTKICH callerów insert_source:
```bash
grep -rn "insert_source" /home/sebastian/personal-ai/app/ --include="*.py"
grep -rn "insert_source" /home/sebastian/personal-ai/scripts/ --include="*.py"
```

5. Upewnij się że KAŻDY caller:
   a. Przekazuje `conn` poprawnie (z pool, nie raw)
   b. Obsługuje zwracany `source_id`
   c. NIE robi osobnego commit (bo insert_source robi commit)

6. Sprawdź czy insert_source w `common/db.py` jest JEDYNĄ definicją — nie może być duplikatu w innym pliku

7. Przetestuj naprawę:
```bash
cd /home/sebastian/personal-ai
# Test direct
.venv/bin/python3 -c "
from app.ingestion.common.db import insert_source
from app.db.postgres import get_pg_connection
with get_pg_connection() as conn:
    sid = insert_source(conn, 'test_source', 'test_name')
    print(f'First call: {sid}')
    sid2 = insert_source(conn, 'test_source', 'test_name')
    print(f'Second call (same): {sid2}')
    assert sid == sid2, 'UPSERT broken!'
    print('OK — upsert works')
    # Cleanup
    with conn.cursor() as cur:
        cur.execute('DELETE FROM sources WHERE source_type = %s', ('test_source',))
    conn.commit()
"

# Test live_ingest doesn't crash
.venv/bin/python3 -m app.ingestion.live_ingest 2>&1 | tail -10

# Test corporate sync
bash scripts/sync_corporate_data.sh 2>&1 | tail -20
```

8. Sprawdź logi po naprawie — powinny przestać crashować:
```bash
tail -5 logs/live_ingest.log
tail -5 logs/sync_corporate_data.log
```

## WAŻNE
- Użyj connection pool (`from app.db.postgres import get_pg_connection`)
- SQL MUSI być parameterized
- NIE zmieniaj sygnatury funkcji jeśli nie musisz (żeby nie popsuć callerów)
- Jeśli sygnatury callerów są niespójne (niektórzy przekazują conn, inni nie) — napraw callerów
