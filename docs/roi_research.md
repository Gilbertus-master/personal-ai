# ROI Monitoring — Research Findings

**Date:** 2026-03-30

## Existing Tables Available for ROI Detection

| Table | Rows | ROI Domain | Key Columns |
|-------|------|------------|-------------|
| `ask_runs` | 230 | Builder/Operational | query_text, latency_ms, cost_usd, model_used |
| `api_costs` | 138,106 | Builder | provider, model, module, cost_usd, tokens |
| `action_items` | 20 | Management/Operational | action_type, status, proposed_at, executed_at |
| `decisions` | 5 | Management | decision_text, area, confidence, decided_at |
| `decision_outcomes` | 0 | Management | actual_outcome, rating |
| `meeting_minutes` | ~varies | Management | meeting_roi_score, decisions_count, action_items_count |
| `standing_orders` | 2 | Management | channel, topic_scope, active |
| `standing_order_metrics` | 0 | Management | sent_count, response_count, avg_response_hours |
| `sent_communications` | ~varies | Management | channel, response_received, response_time_hours |
| `documents` | ~varies | Builder/Operational | metadata, source_type |
| `code_review_findings` | ~varies | Builder | severity, status |

## Existing ROI-Related Modules (5)

1. `app/analysis/meeting_roi.py` — Scores meetings 1-5 (decisions×3 + action_items×2 + commitments×1)
2. `app/analysis/action_outcome_tracker.py` — Response at 24h, follow-up at 72h, closure at 7d
3. `app/analysis/decision_intelligence.py` — Auto-capture decisions, confidence calibration
4. `app/analysis/cost_estimator.py` — LLM-based financial impact estimation
5. `app/analysis/standing_order_effectiveness.py` — Communication effectiveness

## Existing API Endpoints (ROI-related)

- `POST /evaluate` — Person evaluation
- `GET /meeting-roi` — Meeting ROI analysis
- `POST /decisions` — Decision journal
- `POST /decisions/{id}/outcomes` — Decision outcomes

## Connection Pattern
- `from app.db.postgres import get_pg_connection` → context manager from psycopg_pool
- structlog for logging
- Next migration: **019_roi.sql** (016-018 taken)

## 7-Day Stats
- 201 ask_runs, avg latency 40s, total cost $0.26
- 138K API cost records across modules
