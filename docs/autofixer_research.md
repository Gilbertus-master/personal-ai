# Autofixer v2 — Research Findings

## Data (2026-03-29)

### Open findings: 764
| Category | Count |
|---|---|
| correctness | 288 |
| quality | 182 |
| convention | 153 |
| optimization | 73 |
| improvement | 38 |
| security | 30 |

### Fixed: 107
| Category | Fixed |
|---|---|
| correctness | 49 |
| convention | 32 |
| security | 16 |
| optimization | 8 |
| quality | 2 |

### Clusters (>=2 files)
- [high] convention/fetchone() — 2 files
- [low] quality/Missing return type annotations — 2 files
- All other findings are 1-file clusters (title uniqueness)

### Tier1 failures
Tier1 executor returns "No files were modified" for all attempts because:
1. `_fix_print_to_structlog` skips files not under `app/` — most convention findings are in `scripts/`
2. `_fix_print_to_structlog` skips files with `__main__` block — even if they have non-CLI print() calls
3. `_fix_unused_imports` runs ruff F401/F811 but findings may reference imports that ruff considers used
4. Title normalization missing — similar issues get separate clusters

### Potential Tier1 patterns found
- print→structlog: ~5 findings across convention category
- Unused imports: ~2 findings
- Missing structlog: ~1 finding
- Dead code: ~1 finding
- Missing return type annotations: ~2 findings (borderline T1)

### Tier2 stats
- No tier2 attempts logged yet (all clusters assigned tier1 first)
- Budget model: $0.50/1-file, $1.00/2-5, $2.00/6+

## Conclusions
1. Title-based clustering produces too many 1-file clusters — need title normalization
2. Tier1 scope too narrow — need to handle scripts/ and more patterns
3. Most findings (correctness, quality, optimization) are inherently Tier2
4. Fix rate: 107/871 = 12.3% — significant room for improvement
