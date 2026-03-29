# Autofixer v2 — Research (2026-03-29)

## Current State

| Metric | Value |
|--------|-------|
| Total findings | 871 |
| Resolved | 107 (12.3%) |
| Open | 764 |
| Stuck (attempted, not resolved) | 252 |
| Manual review | 0 |
| Success rate | ~30% of attempted |

## Cluster Analysis

Only 2 clusters with 2+ findings by exact (category, title):
- `[high] convention/fetchone() vs fetchall()` → 2 files
- `[low] quality/Missing return type annotations` → 2 files

**Conclusion:** Title-based clustering yields almost no multi-file batches. Category-based tiering is the primary optimization lever.

## Category Distribution (open, non-manual)

| Category | Count |
|----------|-------|
| correctness | 288 |
| quality | 182 |
| convention | 153 |
| optimization | 73 |
| improvement | 38 |
| security | 30 |

## Successfully Fixed Patterns

10 unique patterns fixed so far — all singletons. Mix of correctness, convention, security. No pattern-based batch fixes yet.

## Current Code Architecture

`app/analysis/code_fixer.py`:
- Single-finding-at-a-time model
- `run()` for single, `run_parallel(N)` for N workers on different files
- Each fix = one `claude -p` session ($0.50 budget)
- Verification: ruff check + git diff (no changes = fail)
- Retry: max 6 attempts (3 per round × 2 rounds), then manual_review=true

## Problems Identified

1. **No tiering** — simple fixes (unused imports, print→structlog) burn $0.50 LLM calls when ruff/sed could handle them
2. **No clustering** — same pattern across N files = N separate LLM sessions instead of one
3. **No context enrichment** — LLM doesn't see resolved examples or project conventions
4. **No category-specific strategies** — all findings get identical prompts
5. **High stuck rate** — 252/359 attempted findings stuck = 70% failure on retries

## Existing DB Schema

Columns: id, file_id, file_path, severity, category, title, description, line_start, line_end, suggested_fix, model_used, resolved, resolved_at, created_at, fix_attempted_at, fix_attempt_count, manual_review

**Missing:** cluster_id, tier — need migration.

## Log Analysis

No recent entries in logs/code_fix.log — fixer may not be running or logging elsewhere.
