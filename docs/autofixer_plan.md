# Autofixer v2 — Architecture Plan

## Package: app/analysis/autofixer/

### cluster_manager.py
Groups findings by (category, normalized_title), assigns tiers:
- **Title normalization**: strip file-specific info, collapse similar titles
- **Tier 1** (no LLM): unused-import, print→structlog, dead-code, simple-style
- **Tier 2** (LLM): everything else
- Returns: `[{cluster_id, tier, category, title, findings, file_paths, severity, size}]`

### context_gatherer.py
For Tier2 clusters, builds enriched context:
- `file_contents`: ±20 lines around each finding
- `resolved_similar`: last 3 resolved findings from same category (pattern reference)
- `project_conventions`: psycopg3, structlog, parameterized SQL

### prompt_builder.py
Builds LLM prompt per cluster:
- Multi-file: "fix this pattern in all N files"
- Injects resolved_similar as examples
- Budget: $0.50 (1 file), $1.00 (2-5), $2.00 (6+)

### tier1_executor.py
Deterministic fixes:
- unused imports: ruff --select F401,F811 --fix
- print→structlog: regex swap (app/ AND scripts/ with structlog)
- date format: `$(date)` → `$(date '+%Y-%m-%d %H:%M:%S')` in shell scripts
- Verification: ruff + import check
- On success: mark resolved; on fail: mark attempted

### tier2_executor.py
LLM fixes via claude -p:
- System prompt from scripts/fix_prompt.md
- 2 attempts max; on 2x fail: mark manual_review
- Verification: ruff + git diff

### code_fixer.py (orchestrator)
- `--parallel N`: N workers on clusters
- `--dry-run`: show clusters without fixing
- `--tier1-only` / `--tier2-only`: filter by tier
- Tier1 clusters processed first (fast)
- File-level dedup (two workers don't take same file)
