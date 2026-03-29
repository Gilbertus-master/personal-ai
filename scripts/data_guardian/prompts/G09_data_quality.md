# G09: Data quality checks — volume anomaly, duplicates, consistency

## TASK

### 1. Volume anomaly detection
Stwórz `app/guardian/quality_checks.py`:

**Check 1: Volume drop**
- Porównaj docs imported today vs 7-day average per source
- Jeśli < 30% of average → WARNING (coś może być nie tak)
- Jeśli = 0 i average > 0 → CRITICAL

**Check 2: Volume spike**
- Jeśli > 300% of average → WARNING (duplicate import? loop?)
- Sprawdź czy nie ma zduplikowanych raw_path w documents

**Check 3: Chunk size anomaly**
- Średni rozmiar chunks per source — jeśli odchylenie > 2σ → investigate
- Za małe chunki (< 50 chars) = parser problem
- Za duże chunki (> 5000 chars) = chunking problem

### 2. Duplicate detection
```sql
-- Duplicate documents (same raw_path)
SELECT raw_path, COUNT(*) as dupes FROM documents
GROUP BY raw_path HAVING COUNT(*) > 1;

-- Duplicate chunks (same text in same document)
SELECT document_id, text, COUNT(*) FROM chunks
GROUP BY document_id, text HAVING COUNT(*) > 1;
```
Jeśli dupes > 0 → log WARNING, auto-dedup (keep latest, delete older)

### 3. Consistency checks
- Orphan chunks (chunk bez document): `chunks c LEFT JOIN documents d ON c.document_id=d.id WHERE d.id IS NULL`
- Orphan entities (entity bez chunk): analogicznie
- Events bez valid event_type (nie w 15 allowed types)
- Chunks z embedding_id ale bez wektora w Qdrant

### 4. Freshness consistency
- Porównaj `sources.imported_at` vs `documents.created_at` — jeśli source mówi "fresh" ale docs stare → sync problem

### 5. Run schedule
```
0 5 * * * cd /home/sebastian/personal-ai && .venv/bin/python3 -m app.guardian.quality_checks >> logs/quality_checks.log 2>&1
```
Raz dziennie o 5:00 (przed morning brief)

### 6. Quality score
Wylicz overall quality score (0-100):
- Freshness: 30% weight (all sources within SLA)
- Completeness: 25% (extraction coverage %, embedding coverage %)
- Consistency: 20% (no orphans, no duplicates)
- Volume: 15% (within normal range)
- Error rate: 10% (DLQ size, failed imports)

Zapisz w `ingestion_health` i eksponuj w dashboard.

## WAŻNE
- Auto-dedup: TYLKO dla exact matches (same raw_path AND same text)
- NIE usuwaj danych bez logowania
- Quality checks nie mogą być blocking (read-only na DB)
