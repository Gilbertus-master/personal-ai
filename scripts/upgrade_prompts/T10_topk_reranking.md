# TASK T10: Top-k Increase + BM25 Reranking
**Project:** /home/sebastian/personal-ai
**Status file:** /tmp/gilbertus_upgrade/status/T10.done
**Requires: T8 (hybrid search) must be DONE**

## Context
Current limits in app/api/main.py:
- retrieval: answer_match_limit=8, prefetch_k=30
- summary: 14, prefetch_k=50
- analysis: 18, prefetch_k=70
Too few chunks for complex financial/business queries. After hybrid search (T8), 
we can retrieve more and still get high quality via RRF scoring.

Also need: diversity filter (max 3 chunks per document) and recency boost.

## What to do

### Step 1: Read current limits
```
grep -A 20 "def get_answer_match_limit" /home/sebastian/personal-ai/app/api/main.py
grep -A 20 "def get_prefetch_k" /home/sebastian/personal-ai/app/api/main.py
```

### Step 2: Update get_prefetch_k() in main.py
Change the base values:
```python
def get_prefetch_k(question_type: str, analysis_depth: str) -> int:
    base = {
        "retrieval": 60,    # was 30
        "summary": 120,     # was 50
        "analysis": 150,    # was 70
        "chronology": 150,  # was 100
    }.get(question_type, 80)

    if analysis_depth == "high":
        base = int(base * 1.3)
    elif analysis_depth == "low":
        base = int(base * 0.6)

    return max(base, 30)
```

### Step 3: Update get_answer_match_limit() in main.py
```python
def get_answer_match_limit(question_type: str, analysis_depth: str) -> int:
    base = {
        "retrieval": 15,    # was 8
        "summary": 25,      # was 14
        "analysis": 30,     # was 18
        "chronology": 30,   # was 20
    }.get(question_type, 20)

    if analysis_depth == "high":
        base = int(base * 1.3)
    elif analysis_depth == "low":
        base = int(base * 0.7)

    return max(base, 8)
```

### Step 4: Add diversity filter and recency boost

Add this function in main.py (near other utility functions):

```python
def apply_diversity_and_recency(
    matches: list[dict],
    max_per_doc: int = 3,
    recency_days: int = 30,
    recency_boost: float = 1.1,
) -> list[dict]:
    """
    Post-process matches: 
    1. Recency boost: recent docs get score multiplied by recency_boost
    2. Diversity filter: cap chunks from same document at max_per_doc
    """
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=recency_days)
    
    # Apply recency boost
    for m in matches:
        doc_date = m.get("created_at") or m.get("date")
        if doc_date:
            try:
                if isinstance(doc_date, str):
                    from dateutil.parser import parse
                    doc_date = parse(doc_date)
                if hasattr(doc_date, 'tzinfo') and doc_date.tzinfo is None:
                    doc_date = doc_date.replace(tzinfo=timezone.utc)
                if doc_date >= cutoff:
                    m["score"] = m.get("score", 0) * recency_boost
            except Exception:
                pass
    
    # Re-sort after boost
    matches = sorted(matches, key=lambda x: x.get("score", 0), reverse=True)
    
    # Diversity filter
    doc_counts: dict = {}
    filtered = []
    for m in matches:
        doc_id = m.get("document_id")
        count = doc_counts.get(doc_id, 0)
        if count < max_per_doc:
            filtered.append(m)
            doc_counts[doc_id] = count + 1
    
    return filtered
```

### Step 5: Apply diversity filter in the /ask handler

In main.py, find where `redacted_matches_for_answer` is built (before the answer_question call).
Add the diversity + recency filter:

```python
# After postprocessing, before building redacted_matches_for_answer:
# Apply diversity and recency boost
if len(matches) > 10:  # only if we have enough to filter
    matches = apply_diversity_and_recency(matches, max_per_doc=3, recency_days=30)
```

Find the exact location by searching for `redacted_matches_for_answer` in main.py.

### Step 6: Update max_tokens for larger context

In app/retrieval/answering.py, find max_tokens_map and update:
```python
max_tokens_map = {
    "short": 600,
    "medium": 1400,   # was 1200
    "long": 3000,     # was 2600
}
```

### Step 7: Restart and test
```
systemctl --user restart gilbertus-api
sleep 5

# Test complex financial query
curl -s -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query": "jaki jest cashflow REH i zaległości płatnicze w 2025", "answer_length": "medium", "debug": true}' \
  | python3 -c "
import sys, json; d=json.load(sys.stdin)
m = d.get('meta', {})
print('retrieved:', m.get('retrieved_count'))
print('type:', m.get('question_type'))
print('answer len:', len(d.get('answer','')))
print()
print(d.get('answer','')[:500])
"
```
Expected: retrieved_count should be 15-30 (was 8-14).

### Step 8: Commit
```
cd /home/sebastian/personal-ai
git add app/api/main.py app/retrieval/answering.py
git commit -m "feat(retrieval): increase top-k limits and add diversity/recency filter

- retrieval: 8→15 chunks, summary: 14→25, analysis: 18→30
- Diversity filter: max 3 chunks per document 
- Recency boost: 1.1x for docs from last 30 days
- Larger max_tokens for medium/long answers"
```

## Completion
```
echo "done" > /tmp/gilbertus_upgrade/status/T10.done
openclaw system event --text "Upgrade T10 done: top-k increased with diversity+recency filter" --mode now
```
