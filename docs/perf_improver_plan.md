# Performance Improver — Plan

**Date:** 2026-03-30

## A. Bottleneck Classification Rules

Based on `stage_ms` JSONB in `ask_runs`:

| Condition | Type | Priority |
|-----------|------|----------|
| `interpret_ms > 3000` | `slow_interpret` | Medium |
| `retrieve_ms > 5000` | `slow_retrieve` | Medium |
| `answer_ms > 15000` | `slow_answer` | High |
| `total > 30000` | `very_slow_query` | High |
| `error_rate > 5%` | `high_errors` | Critical |
| `cache_hit_rate < 30%` | `low_cache` | Low |
| `high_depth_pct > 60%` | `excessive_high_depth` | Medium |

## B. Fix Strategies

Each strategy = one concrete, reversible change:

| Bottleneck | Fix | File/Param | Before → After |
|------------|-----|------------|----------------|
| `slow_interpret` | Increase cache TTL | `INTERPRETATION_CACHE_TTL` | 300 → 600 |
| `slow_retrieve` + no routing | Enable tool routing | `ENABLE_TOOL_ROUTING` | false → true |
| `slow_answer` + high context | Reduce max context | `MAX_CONTEXT_CHARS` | 80000 → 60000 |
| `excessive_high_depth` | Cap default depth | query_interpreter.py prompt | high → normal for simple queries |
| `low_cache` | Increase cache TTL | `INTERPRETATION_CACHE_TTL` | 300 → 900 |

**Rule: max 1 fix per run.** Priority order: high_errors > slow_answer > slow_retrieve > slow_interpret > low_cache.

## C. Architecture

```
app/analysis/perf_improver/
  __init__.py
  query_analyzer.py       # Fetches & aggregates ask_runs stats for 24h window
  bottleneck_detector.py  # Classifies bottleneck type from aggregated stats
  fix_planner.py          # Selects fix strategy, checks if already applied
  improvement_agent.py    # Orchestrates: analyze → detect → plan → apply → verify → commit/revert

scripts/daily_perf_improvement.sh   # Cron wrapper
```

## D. DB Table

```sql
CREATE TABLE IF NOT EXISTS perf_improvement_journal (
    id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL,
    bottleneck_type TEXT NOT NULL,
    fix_applied TEXT NOT NULL,
    param_changed TEXT,
    old_value TEXT,
    new_value TEXT,
    latency_before_ms INTEGER,
    latency_after_ms INTEGER,
    improvement_pct NUMERIC(5,1),
    committed BOOLEAN DEFAULT FALSE,
    reverted BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## E. Verification Protocol

After each fix:
1. Run 3 test queries via `/ask` (short, normal, high depth)
2. Measure latency from response
3. Compare with 24h baseline from ask_runs
4. If improvement >= 10% → git commit the change
5. If no improvement or regression → revert changed file/param
6. Log result to `perf_improvement_journal`

## F. Cron

```
# CET 03:00 = UTC 01:00 (summer) or UTC 02:00 (winter)
0 2 * * * cd /home/sebastian/personal-ai && bash scripts/daily_perf_improvement.sh >> logs/perf_improvement.log 2>&1
```

## G. Safety

- Never modify non_regression_gate.py
- Never modify .env permanently — use env var override in subprocess
- Always revert on failed verification
- Max 1 change per run
- All changes logged to journal table
