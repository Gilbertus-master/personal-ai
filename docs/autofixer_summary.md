# Autofixer v2 — Summary (2026-03-29)

## Co zbudowano

### Nowy pakiet: `app/analysis/autofixer/`

| Moduł | Opis |
|-------|------|
| `cluster_manager.py` | Grupuje findings po (category, title), przypisuje tier 1/2, zapisuje do DB |
| `context_gatherer.py` | Zbiera kontekst: ±20 linii kodu, resolved examples, project conventions |
| `prompt_builder.py` | Buduje prompt LLM z kontekstem, multi-file support, dynamiczny budget |
| `tier1_executor.py` | Deterministic fixes: ruff F401/F811, print→structlog (bez LLM) |
| `tier2_executor.py` | LLM fixes: claude -p z enriched context, retry z error feedback |

### Refaktored: `app/analysis/code_fixer.py`
- Nowe CLI: `--dry-run`, `--tier1-only`, `--tier2-only`, `--parallel N`
- Flow: build_clusters → sort by tier/severity → parallel fix workers

### DB Migration: `scripts/migrations/015_autofixer_v2.sql`
- Nowe kolumny: `cluster_id TEXT`, `tier INTEGER`

### Updated: `scripts/fix_prompt.md`
- Sekcje: Cluster fixes, Examples from this project

## Top klastry (dry-run)

| Tier | Count | Opis |
|------|-------|------|
| Tier 1 | 25 clusters | print→structlog (21), unused imports (2), logging→structlog (2) |
| Tier 2 | 587 clusters | correctness (288), quality (182), convention (128), optimization (73), security (30) |
| **Total** | **612 clusters** | **614 findings** |

## Szacowany impact

- **Tier 1 (25 findings):** 100% fixable bez LLM → oszczędność ~$12.50 vs claude -p sessions
- **Tier 2 z context enrichment:** Szacowany wzrost success rate z ~30% do ~50-60% dzięki:
  - Resolved examples jako wzorce (LLM widzi jak to naprawiono wcześniej)
  - Project conventions wstrzyknięte w prompt (mniej convention violations)
  - Multi-file cluster batching (jeden prompt na wzorzec)
  - Retry z error feedback ("Previous attempt failed: X")

## Jak uruchomić

```bash
# Dry run — pokaż klastry
python -m app.analysis.code_fixer --dry-run

# Tylko tier 1 (szybkie, bez LLM)
python -m app.analysis.code_fixer --parallel 8 --tier1-only

# Tylko tier 2 (LLM)
python -m app.analysis.code_fixer --parallel 4 --tier2-only

# Pełny run (tier 1 + tier 2)
python -m app.analysis.code_fixer --parallel 8

# Cron (istniejący script)
bash scripts/code_fix_parallel.sh 8
```

## Non-regression
- ✅ ruff check: All checks passed
- ✅ Non-regression gate: 15 metrics OK
- ✅ API health: ok
- ✅ Import verification: all 5 modules + code_fixer OK
