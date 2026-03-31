# TASK T8: Hybrid Search BM25 (tsvector + GIN + Reciprocal Rank Fusion)
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T8.done
**CRITICAL - blocks T10, T18**

## Context
Current search: only vector search (OpenAI embeddings via Qdrant).
Keyword fallback exists but uses ILIKE (slow, no index, no ranking).
Problem: for queries with proper names (Roch, Diana, REH, GoldenPeaks, Kuźmiński),
vector search misses exact matches. We need BM25/FTS as a second retrieval leg.

Target: Reciprocal Rank Fusion (RRF) combining vector ranks + BM25 ranks.
RRF formula: score = 1/(60 + rank_vector) + 1/(60 + rank_bm25)

Key files:
- /home/sebastian/personal-ai/app/retrieval/retriever.py (main changes here)
- PostgreSQL chunks table (add tsvector column + GIN index)

## What to do

### Step 1: Read current retriever.py structure
```
grep -n "def \|class " /home/sebastian/personal-ai/app/retrieval/retriever.py
```

### Step 2: Add tsvector column to chunks
```
docker exec gilbertus-postgres psql -U gilbertus -c "
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS text_tsv tsvector
GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text, ''))) STORED;"
```

Note: Use 'simple' not 'polish' - Polish FTS config may not be installed.
Verify it works: the ALTER TABLE might take a few minutes for 105k rows.
```
docker exec gilbertus-postgres psql -U gilbertus -c "SELECT text_tsv FROM chunks LIMIT 1;" 2>&1 | head -3
```

### Step 3: Create GIN index (runs in background)
```
docker exec gilbertus-postgres psql -U gilbertus -c "
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_text_tsv ON chunks USING GIN(text_tsv);"
```
This will take ~10-15 minutes for 105k rows. It runs CONCURRENTLY (non-blocking).
Monitor: `docker exec gilbertus-postgres psql -U gilbertus -c "SELECT schemaname, tablename, indexname, indexdef FROM pg_indexes WHERE indexname='idx_chunks_text_tsv';" 2>/dev/null`

While index is building, proceed with code changes.

### Step 4: Add BM25 search function to retriever.py

Open /home/sebastian/personal-ai/app/retrieval/retriever.py and add this function
AFTER the existing `_keyword_search_fallback` function:

```python
def _bm25_search(
    query: str,
    top_k: int = 50,
    source_types: list[str] | None = None,
    source_names: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Full-text search using PostgreSQL tsvector + ts_rank (BM25-like).
    Returns results sorted by relevance with rank scores."""
    # Build tsquery from query terms
    # Use plainto_tsquery for robustness (handles multi-word, punctuation)
    where_clauses = ["c.text_tsv @@ plainto_tsquery('simple', %s)", "c.text IS NOT NULL"]
    params: list = [query]

    if source_types:
        placeholders = ",".join(["%s"] * len(source_types))
        where_clauses.append(f"s.source_type IN ({placeholders})")
        params.extend(source_types)

    if source_names:
        placeholders = ",".join(["%s"] * len(source_names))
        where_clauses.append(f"s.source_name IN ({placeholders})")
        params.extend(source_names)

    if date_from:
        where_clauses.append("d.created_at >= %s")
        params.append(date_from)

    if date_to:
        where_clauses.append("d.created_at <= %s")
        params.append(date_to)

    params.append(top_k)

    sql = f"""
        SELECT
            c.id as chunk_id,
            c.document_id,
            c.text,
            s.source_type,
            s.source_name,
            d.title,
            d.created_at,
            ts_rank(c.text_tsv, plainto_tsquery('simple', %s)) as bm25_score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY bm25_score DESC
        LIMIT %s
    """
    # ts_rank needs query repeated
    all_params = [query] + params

    results = []
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, all_params)
                for row in cur.fetchall():
                    results.append({
                        "chunk_id": row[0],
                        "document_id": row[1],
                        "text": row[2] or "",
                        "source_type": row[3],
                        "source_name": row[4],
                        "title": row[5],
                        "date": str(row[6]) if row[6] else None,
                        "score": float(row[7]),
                        "search_type": "bm25",
                    })
    except Exception as e:
        import structlog as _sl
        _sl.get_logger().warning("bm25_search.failed", error=str(e))
    return results


def _rrf_merge(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion: combine vector and BM25 results.
    RRF score = 1/(k + rank_vector) + 1/(k + rank_bm25)
    Higher is better.
    """
    rrf_scores: dict[int, float] = {}
    result_map: dict[int, dict] = {}

    # Vector results ranked by position
    for rank, item in enumerate(vector_results, 1):
        cid = item.get("chunk_id")
        if cid is None:
            continue
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)
        result_map[cid] = item

    # BM25 results ranked by position
    for rank, item in enumerate(bm25_results, 1):
        cid = item.get("chunk_id")
        if cid is None:
            continue
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in result_map:
            result_map[cid] = item

    # Sort by RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    merged = []
    for cid in sorted_ids:
        item = result_map[cid].copy()
        item["score"] = rrf_scores[cid]
        item["search_type"] = "hybrid_rrf"
        merged.append(item)

    return merged
```

### Step 5: Modify search_chunks() to use hybrid search

Find the `search_chunks()` function in retriever.py.
Add hybrid search AFTER the vector search succeeds (before return).

Look for where `hits` are processed and `enriched` list is built.
After building `enriched`, add BM25 and merge:

```python
    # After building 'enriched' list from vector search:
    
    # Hybrid: also run BM25 search and merge via RRF
    try:
        bm25_hits = _bm25_search(
            query=query,  # use original query, not expanded
            top_k=limit,
            source_types=source_types,
            source_names=source_names,
            date_from=date_from,
            date_to=date_to,
        )
        if bm25_hits:
            # Fetch metadata for BM25 results not already in enriched
            bm25_doc_ids = [h["document_id"] for h in bm25_hits if h["document_id"] not in {e["document_id"] for e in enriched}]
            if bm25_doc_ids:
                extra_meta = fetch_document_metadata(bm25_doc_ids)
                for hit in bm25_hits:
                    if hit["document_id"] in extra_meta:
                        hit.update(extra_meta[hit["document_id"]])
            
            enriched = _rrf_merge(enriched, bm25_hits)
    except Exception as _e:
        import structlog as _sl
        _sl.get_logger().warning("hybrid_search.bm25_failed", error=str(_e))
        # Fall through to vector-only results
```

You need to read the actual search_chunks() code carefully first and integrate at the right place.
The key is: vector results go in as `enriched`, BM25 results go in as `bm25_hits`, 
`_rrf_merge()` produces the final `enriched` list.

Then apply source_type filtering and top_k slicing AFTER the merge.

### Step 6: Verify GIN index is built
```
docker exec gilbertus-postgres psql -U gilbertus -c "
SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes WHERE tablename='chunks';"
```

### Step 7: Test hybrid search
```
systemctl --user restart gilbertus-api
sleep 5

# Test with a proper name query
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query": "rozmowy z Rochem Baranowskim o cashflow", "answer_length": "medium", "debug": true}' \
  | python3 -c "
import sys, json; d=json.load(sys.stdin)
print('retrieved:', d.get('meta',{}).get('retrieved_count'))
print('answer preview:', d.get('answer','')[:300])
"
```

### Step 8: Commit
```
cd /home/sebastian/personal-ai
git add app/retrieval/retriever.py
git commit -m "feat(retrieval): add hybrid search BM25+vector RRF fusion

- Add tsvector column to chunks table (GIN indexed)
- New _bm25_search() function using PostgreSQL FTS
- New _rrf_merge() for Reciprocal Rank Fusion
- search_chunks() now combines vector + BM25 results
- Expected +30-40% recall for proper noun queries"
```

## Completion
```
echo "done" > /tmp/gilbertus_upgrade/status/T8.done
openclaw system event --text "Upgrade T8 done: hybrid BM25+vector search active" --mode now
```
