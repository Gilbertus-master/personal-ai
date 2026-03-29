# ROI Monitoring Module — Plan

**Date:** 2026-03-30

## A. DB Schema

```sql
-- Hierarchy: owner > company > department > team > user
roi_hierarchy (
    id BIGSERIAL PK,
    name TEXT NOT NULL,
    type TEXT CHECK (type IN ('owner','company','department','team','user')),
    parent_id BIGINT REFERENCES roi_hierarchy(id),
    hourly_rate_pln NUMERIC(10,2) DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Individual activities generating value
roi_activities (
    id BIGSERIAL PK,
    entity_id BIGINT REFERENCES roi_hierarchy(id),
    activity_type TEXT NOT NULL,
    domain TEXT CHECK (domain IN ('builder','management','life','operational')),
    value_pln NUMERIC(12,2) DEFAULT 0,
    time_saved_min INTEGER DEFAULT 0,
    description TEXT,
    source_table TEXT,
    source_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Weekly/monthly rollups per hierarchy node
roi_summaries (
    id BIGSERIAL PK,
    entity_id BIGINT REFERENCES roi_hierarchy(id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    domain TEXT,
    total_value_pln NUMERIC(14,2) DEFAULT 0,
    synergy_bonus_pln NUMERIC(14,2) DEFAULT 0,
    breakdown JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_id, period_start, period_end, domain)
)
```

## B. Value Mapping

| Source | Activity Type | Domain | Default Value |
|--------|--------------|--------|---------------|
| ask_runs | query_answered | operational | 30 min × hourly_rate |
| ask_runs (Sebastian) | query_answered | builder | 30 min × hourly_rate |
| decisions | decision_made | management | 60 min × hourly_rate |
| action_items (executed) | action_executed | management | 45 min × hourly_rate |
| code_review_findings (resolved) | code_fix | builder | severity-based (30-120 min) |
| documents ingested | knowledge_added | builder | 15 min × hourly_rate |
| meeting_minutes (with ROI) | meeting_productive | management | roi_score × 30 min × rate |
| sent_communications | communication_sent | management | 20 min × hourly_rate |

## C. Module Architecture

```
app/analysis/roi/
  __init__.py              — exports
  hierarchy.py             — CRUD for roi_hierarchy tree
  value_mapper.py          — maps activities to PLN values
  activity_tracker.py      — auto-detects activities from existing tables
  synergy_calculator.py    — cross-entity bonus when insight helps multiple users
  roi_reporter.py          — generates summaries (weekly/monthly)

app/api/roi.py             — API endpoints
migrations/019_roi.sql     — schema + seed data
```

## D. API Endpoints

```
GET  /roi/summary?entity_id=&period=week|month    — ROI summary for entity
GET  /roi/builder?period=week|month                — Builder ROI (Sebastian)
GET  /roi/management?period=week|month             — Management ROI
GET  /roi/life?period=week|month                   — Life ROI
GET  /roi/company/{id}?period=month                — Company-level aggregation
GET  /roi/leaderboard                              — User ranking by ROI
POST /roi/activity                                 — Manual activity logging
GET  /roi/hierarchy                                — Hierarchy tree
POST /roi/hierarchy                                — Add hierarchy node
```

## E. Auto-Detection Sources

1. `ask_runs` → every query = operational/builder ROI
2. `decisions` → every decision = management ROI
3. `action_items` (status=executed) → management ROI
4. `code_review_findings` (resolved) → builder ROI
5. `documents` (new) → builder ROI (knowledge base growth)
6. `meeting_minutes` (with roi_score) → management ROI
7. `sent_communications` → management ROI

## F. Configurable Rates (.env)

```
ROI_RATE_OWNER_PLN=600        # Sebastian: 600 PLN/h
ROI_RATE_SENIOR_PLN=300       # Senior manager
ROI_RATE_EMPLOYEE_PLN=150     # Regular employee
ROI_DEFAULT_QUERY_MINUTES=30  # Minutes saved per query
ROI_DEFAULT_DECISION_MINUTES=60
ROI_DEFAULT_ACTION_MINUTES=45
```
