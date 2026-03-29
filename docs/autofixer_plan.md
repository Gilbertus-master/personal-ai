# Autofixer v2 — Plan (2026-03-29)

## Architecture: `app/analysis/autofixer/`

### A. cluster_manager.py

**Purpose:** Group findings into clusters and assign tiers.

```python
build_clusters() -> list[dict]
```

Each cluster:
```python
{
    "cluster_id": "convention__fetchone_violation__2",
    "category": "convention",
    "title": "fetchone() used instead of fetchall()",
    "tier": 1 | 2,
    "findings": [finding_dict, ...],
    "file_paths": ["app/foo.py", "app/bar.py"],
}
```

**Tier assignment:**
- **Tier 1 (no LLM):** Deterministic fixes via ruff/sed:
  - `category='convention'` AND title matches `unused import` or `unused variable`
  - `category='convention'` AND title matches `print()` / `print statement` / `structlog`
  - These are fixable with `ruff check --select F401,F811 --fix` or simple regex
- **Tier 2 (LLM):** Everything else

**Clustering logic:**
- Group by (category, title) — findings with identical category+title form a cluster
- Singletons (1 finding) still go through the pipeline as cluster_size=1
- Limit cluster size to 10 files max (split larger clusters)

### B. context_gatherer.py

**Purpose:** Enrich cluster with context for LLM.

```python
gather_cluster_context(cluster: dict) -> dict
```

Returns:
```python
{
    "file_contents": {"path": "±20 lines around finding"},
    "resolved_similar": [resolved_finding_dicts],  # up to 3
    "project_conventions": str,  # static block
    "cluster_size": int,
}
```

- `file_contents`: For each finding in cluster, read ±20 lines around line_start
- `resolved_similar`: `SELECT * FROM code_review_findings WHERE resolved=TRUE AND category=%s AND title LIKE %s LIMIT 3`
- `project_conventions`: Static string with psycopg3, structlog, parameterized SQL, get_pg_connection rules

### C. prompt_builder.py

**Purpose:** Build LLM prompt from cluster + context.

```python
build_fix_prompt(cluster: dict, context: dict) -> str
```

- For multi-file clusters: "Fix THIS PATTERN across ALL N files in one session"
- Inject resolved_similar as worked examples
- Inject project_conventions
- Budget: $0.50 for 1 file, $1.00 for 2-5 files, $2.00 for 6+ files

### D. tier1_executor.py

**Purpose:** Fix tier-1 findings without LLM.

```python
execute_tier1(cluster: dict) -> dict
```

Strategies:
- **Unused imports:** `ruff check --select F401 --fix <file>`
- **Unused variables:** `ruff check --select F811 --fix <file>`
- **print→structlog:** Regex replacement in files

Verification: `python3 -c "import <module>"` + `ruff check`
On success: mark all findings in cluster as resolved.

### E. tier2_executor.py

**Purpose:** Fix tier-2 findings via Claude LLM session.

```python
execute_tier2(cluster: dict, context: dict, prompt: str) -> dict
```

- Launch `claude -p` with prompt from prompt_builder
- CLAUDE_BIN from env, model from CODE_FIX_MODEL
- Budget: $0.50/$1.00/$2.00 based on cluster_size
- Verification: ruff + import check
- On success: mark resolved
- On first fail: retry with "Previous attempt failed: <error>. Try different approach."
- On second fail: mark manual_review=true, move on

### F. Refactored code_fixer.py

**CLI:**
```bash
python -m app.analysis.code_fixer [--parallel N] [--dry-run] [--tier1-only] [--tier2-only]
```

- `--dry-run`: Show clusters + tiers without fixing
- `--parallel N`: N workers (default 8)
- `--tier1-only` / `--tier2-only`: Run only specified tier

**Flow:**
1. `build_clusters()` → list of clusters
2. Sort: Tier 1 first, then Tier 2 by severity
3. Workers process clusters (file-level locking via exclude_files)

### G. Updated scripts/fix_prompt.md

Add sections:
- "Cluster fix" instructions for multi-file patterns
- "Examples from this project" (dynamically filled by prompt_builder)
- "Previous similar fixes" (dynamically filled)

## DB Migration

New columns needed on `code_review_findings`:
- `cluster_id TEXT` — assigned during clustering (ephemeral, overwritten each run)
- `tier INTEGER` — 1 or 2

Migration: `scripts/migrations/015_autofixer_v2.sql`

## Feasibility Assessment

- **Tier 1:** Very feasible — ruff handles F401/F811 natively. Print→structlog needs careful regex but is bounded.
- **Tier 2:** Main improvement is context enrichment (resolved examples + conventions). This should reduce the 70% stuck rate significantly.
- **Clustering:** With only 2 multi-file clusters currently, the main benefit is future-proofing. Immediate value comes from tiering + context.
- **Risk:** Tier 1 print→structlog replacement could break code if print() is used for CLI output. Mitigation: only replace in files under `app/` that already import structlog.
