# Performance Improver — Research Findings

**Date:** 2026-03-30

## 1. ask_runs Schema

| Column | Type | Notes |
|--------|------|-------|
| id | bigint | PK |
| query_text | text | Original query |
| normalized_query | text | After interpretation |
| question_type | text | e.g. factual, chronology |
| analysis_depth | text | low / normal / high |
| latency_ms | integer | Total end-to-end |
| stage_ms | jsonb | Per-stage breakdown |
| error_flag | boolean | |
| cache_hit | boolean | |
| model_used | text | e.g. claude-sonnet-4-6 |
| input_tokens / output_tokens | integer | |
| cost_usd | numeric | |
| created_at | timestamptz | |

**Total rows:** 230

## 2. Stage Breakdown (stage_ms JSONB)

Stages available: `interpret`, `retrieve`, `answer`, `evaluate` (optional).

Sample:
```json
{"total": 22967, "answer": 17039, "evaluate": 2512, "retrieve": 945, "interpret": 2455}
{"total": 2903, "retrieve": 1097, "interpret": 1797}
{"total": 8447, "answer": 6711, "retrieve": 460, "interpret": 1270}
```

## 3. Current Performance (24h snapshot, 2026-03-30)

| Metric | Value |
|--------|-------|
| Total runs | 7 |
| Avg latency | 13,912 ms |
| P95 latency | 27,075 ms |
| Max latency | 28,835 ms |
| Error rate | 0% |
| Cache hit rate | 0% |

### Bottleneck from /observability/dashboard:
- **avg_answer_ms = 9,931 ms (76.5% of total)** ← dominant bottleneck
- avg_interpret_ms = 1,993 ms
- avg_retrieve_ms = 1,058 ms

## 4. Analysis Depth Distribution (all-time)

| Depth | Count | Avg latency_ms |
|-------|-------|----------------|
| normal | 105 | 23,327 |
| high | 100 | 71,323 |
| low | 25 | 9,830 |

**Key insight:** `high` depth queries are 3x slower than `normal` and 7x slower than `low`. The `high` depth triggers alternate_queries and sub_questions which multiply retrieval+answer calls.

## 5. Configurable Parameters

| Parameter | Location | Current Default | Effect |
|-----------|----------|-----------------|--------|
| `INTERPRETATION_CACHE_TTL` | .env / query_interpreter.py | 300s (5 min) | Cache interpreted queries |
| `ENABLE_TOOL_ROUTING` | .env / tool_router.py | false | Smart source routing |
| `MAX_CONTEXT_CHARS` | .env / main.py:980 | 80,000 | Truncate context for answer stage |
| `ANTHROPIC_FAST_MODEL` | .env / orchestrator.py | claude-haiku-4-5 | Model for interpretation |
| `analysis_depth` | query_interpreter.py | auto-detected | Drives query complexity |

## 6. Slowest Queries (all-time)

1. **541,642 ms** — "architektura techniczna Gilbertus API..." (depth=high, broad topic)
2. **185,216 ms** — "Jak zmieniała się moja sytuacja życiowa..." (chronology, depth=high)
3. **179,381 ms** — "Transformacja Cyfrowa budżet koszty..." (multi-entity, depth=high)

All slowest queries are `analysis_depth=high`.

## 7. Conclusions

1. **Primary bottleneck: answer stage (76.5%)** — LLM generation with large context
2. **Secondary: high analysis_depth** causes 3x latency via sub-questions
3. **Cache hit rate = 0%** — interpretation cache exists but TTL may be too short
4. **Tool routing disabled** — could reduce irrelevant sources in retrieve stage
5. **MAX_CONTEXT_CHARS=80,000** could be reduced to 60,000 for normal queries
