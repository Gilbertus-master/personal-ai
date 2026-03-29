# Autofixer v2 — Summary

## What was built
Complete autofixer v2 pipeline with tiering, clustering, and internal pattern research.

### Package: app/analysis/autofixer/ (5 modules)
1. **cluster_manager.py** — groups findings by normalized (category+title), assigns tier 1/2
2. **context_gatherer.py** — enriches clusters with file context and resolved examples
3. **prompt_builder.py** — builds multi-file LLM prompts with examples and conventions
4. **tier1_executor.py** — deterministic fixes (ruff, regex) without LLM
5. **tier2_executor.py** — LLM-based fixes via claude -p with retry logic

### Orchestrator: app/analysis/code_fixer.py
- Parallel execution (default 8 workers)
- Tier1 first (fast), then Tier2
- CLI: `python -m app.analysis.code_fixer --parallel 8 --dry-run`

### Cron: scripts/code_fix_parallel.sh
- Every 10 min during 8-22 CET, 8 workers
- Lock file prevents concurrent runs

## Top clusters found
| Severity | Category | Pattern | Files |
|---|---|---|---|
| high | convention | fetchone() vs fetchall() | 2 |
| low | quality | Missing return type annotations | 2 |
| medium | correctness | Various (1-file clusters) | 288 |

## Stats
- 764 open findings, 107 previously fixed
- Tier1 potential: ~10 findings (print, unused imports, dead code)
- Tier2 potential: ~754 findings
- Estimated cost per full run: ~$50-100 (budget-capped per cluster)

## Impact
- Automated triage: findings classified into tiers automatically
- Cluster efficiency: same-pattern fixes batched together
- Cost control: budget caps per cluster size
- Quality gates: ruff + import verification before marking resolved
- Retry logic: 2 attempts before escalating to manual_review
