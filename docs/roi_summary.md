# ROI Monitoring Module — Summary

**Deployed:** 2026-03-30

## Schema (3 tables)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `roi_hierarchy` | Org tree: owner → company → department → team → user | name, type, parent_id, hourly_rate_pln |
| `roi_activities` | Individual value-generating activities | entity_id, activity_type, domain, value_pln, time_saved_min |
| `roi_summaries` | Period rollups per entity + domain | entity_id, period_start/end, total_value_pln, synergy_bonus_pln, breakdown (JSONB) |

## API Endpoints (10)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/roi/summary?entity_id=&period=week\|month\|quarter` | ROI summary (default: owner) |
| GET | `/roi/builder?period=` | Builder ROI (system development) |
| GET | `/roi/management?period=` | Management ROI (delegation/decisions) |
| GET | `/roi/life?period=` | Life ROI (personal affairs) |
| GET | `/roi/company/{id}?period=` | Company-level aggregation |
| GET | `/roi/leaderboard?period=&limit=` | Entity ranking by ROI |
| POST | `/roi/activity` | Manual activity logging |
| POST | `/roi/scan?since=` | Trigger auto-detection scan |
| GET | `/roi/hierarchy` | Full org hierarchy |
| POST | `/roi/hierarchy` | Add hierarchy node |

## Domains

| Domain | Who | What's measured |
|--------|-----|----------------|
| **builder** | Sebastian | Features shipped, queries (as system validation), code fixes, knowledge base growth |
| **management** | Sebastian | Decisions, actions delegated, meetings, communications |
| **life** | Sebastian | Personal affairs assisted (manual logging) |
| **operational** | REH/REF users | Queries answered, actions executed (post-Omnius) |

## Auto-Detection Sources

Activities are auto-detected from 7 existing tables:
- `ask_runs` → query_answered
- `decisions` → decision_made
- `action_items` (executed) → action_executed
- `code_review_findings` (resolved) → code_fix
- `documents` → knowledge_added
- `meeting_minutes` (scored) → meeting_productive
- `sent_communications` → communication_sent

Run scan: `POST /roi/scan` or `python3 -c "from app.analysis.roi.activity_tracker import scan_and_record_activities; print(scan_and_record_activities())"`

## Value Mapping (Configurable via .env)

| Variable | Default | Description |
|----------|---------|-------------|
| `ROI_RATE_OWNER_PLN` | 600 | Sebastian's hourly rate |
| `ROI_RATE_SENIOR_PLN` | 300 | Senior manager rate |
| `ROI_RATE_EMPLOYEE_PLN` | 150 | Employee rate |
| `ROI_DEFAULT_QUERY_MINUTES` | 30 | Time saved per query |
| `ROI_DEFAULT_DECISION_MINUTES` | 60 | Time saved per decision |
| `ROI_DEFAULT_ACTION_MINUTES` | 45 | Time saved per action |

## Example Output

```json
GET /roi/summary?period=month

{
  "entity_id": 1,
  "period_start": "2026-03-01",
  "period_end": "2026-04-01",
  "total_value_pln": 72000.0,
  "synergy_bonus_pln": 0.0,
  "grand_total_pln": 72000.0,
  "total_time_saved_hours": 120.0,
  "breakdown": {
    "builder": {
      "subtotal_pln": 69000.0,
      "activities": [{"type": "query_answered", "count": 230, "value_pln": 69000.0}]
    },
    "management": {
      "subtotal_pln": 3000.0,
      "activities": [{"type": "decision_made", "count": 5, "value_pln": 3000.0}]
    }
  }
}
```

## How to Read Metrics

- **total_value_pln** = sum of all activities × rate × time_saved
- **synergy_bonus_pln** = 15% bonus per additional entity/domain sharing an insight
- **grand_total_pln** = total_value + synergy_bonus
- **breakdown** = per-domain detail with activity types, counts, and values
- **time_saved_hours** = total hours saved by automation

## Hierarchy (seeded)

```
Sebastian Jabłoński (owner, 600 PLN/h)
├── REH (Respect Energy Holding) (company)
└── REF (Respect Energy Fuels) (company)
```

Add users via `POST /roi/hierarchy` when Omnius is deployed.

## Files

```
migrations/019_roi.sql           — schema + seed
app/analysis/roi/__init__.py     — exports
app/analysis/roi/hierarchy.py    — org tree CRUD
app/analysis/roi/value_mapper.py — activity → PLN conversion
app/analysis/roi/activity_tracker.py — auto-detection from 7 tables
app/analysis/roi/synergy_calculator.py — cross-entity/domain bonus
app/analysis/roi/roi_reporter.py — summary generation + persistence
app/api/roi.py                   — 10 API endpoints
```
