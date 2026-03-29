# Performance Improvement Loop — Summary

**Date:** 2026-03-30

## How It Works

Daily at 02:00 UTC (03:00/04:00 CET), the agent runs automatically:

1. **Analyze** — fetches 24h of `ask_runs` stats (latency, stages, errors, cache hits)
2. **Detect** — classifies the dominant bottleneck (slow_answer, slow_retrieve, slow_interpret, low_cache, etc.)
3. **Plan** — selects a concrete, reversible fix (env var change)
4. **Apply** — modifies `.env` parameter
5. **Verify** — runs 3 test queries, measures avg latency
6. **Decide** — if improvement >= 10% → git commit; otherwise → revert
7. **Log** — writes result to `perf_improvement_journal` table

## Bottleneck Types

| Type | Trigger | Auto-Fix |
|------|---------|----------|
| `high_errors` | error_rate > 5% | Manual investigation (no auto-fix) |
| `very_slow_query` | P95 > 30s | Reduce MAX_CONTEXT_CHARS |
| `slow_answer` | avg_answer > 15s | Reduce MAX_CONTEXT_CHARS |
| `slow_retrieve` | avg_retrieve > 5s | Enable TOOL_ROUTING |
| `slow_interpret` | avg_interpret > 3s | Increase INTERPRETATION_CACHE_TTL |
| `low_cache` | cache_hit < 30% | Increase INTERPRETATION_CACHE_TTL |
| `excessive_high_depth` | high_depth > 60% | Increase cache TTL |

## Files

```
app/analysis/perf_improver/
  __init__.py
  query_analyzer.py       — fetches & aggregates ask_runs stats
  bottleneck_detector.py  — classifies bottleneck type
  fix_planner.py          — selects fix strategy (skips recently-applied)
  improvement_agent.py    — orchestrates full loop

scripts/daily_perf_improvement.sh  — cron wrapper
```

## Example Dry-Run Output

```json
{
  "status": "dry_run",
  "bottleneck": "low_cache",
  "fix": "Triple interpretation cache TTL from 300s to 900s",
  "param": "INTERPRETATION_CACHE_TTL",
  "old": "300",
  "new": "900",
  "baseline_ms": 12268
}
```

## Manual Usage

```bash
# Dry run (analyze only, no changes)
source .venv/bin/activate
python3 -m app.analysis.perf_improver.improvement_agent --dry-run

# Full run (applies fix if beneficial)
python3 -m app.analysis.perf_improver.improvement_agent

# Check journal
docker exec gilbertus-postgres psql -U gilbertus -d gilbertus -c \
  "SELECT run_date, bottleneck_type, fix_applied, improvement_pct, committed, reverted FROM perf_improvement_journal ORDER BY id DESC LIMIT 10;"
```

## Safety

- Max 1 change per run
- Skips fixes applied in last 7 days
- Reverts immediately if improvement < 10%
- Reverts if verification queries fail
- All results logged to DB journal
- Non-regression gate passes
