"""Finance adapter — collects budget/actuals from a local finance mirror."""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg
import structlog

from process_collector.adapters.base import BaseProcessAdapter

logger = structlog.get_logger(__name__)

_METRICS_QUERY = """
WITH week_bounds AS (
    SELECT %(week_start)s::date AS ws,
           (%(week_start)s::date + INTERVAL '7 days') AS we
),
actuals AS (
    SELECT * FROM finance_ledger, week_bounds
    WHERE posting_date >= ws AND posting_date < we
      AND (%(cost_centers)s = '{}' OR cost_center = ANY(%(cost_centers)s))
),
budget AS (
    SELECT * FROM finance_budget
    WHERE period_start <= %(week_start)s AND period_end >= %(week_start)s
      AND (%(cost_centers)s = '{}' OR cost_center = ANY(%(cost_centers)s))
)
SELECT
    COALESCE(SUM(a.amount), 0) AS actual_cost,
    COALESCE((SELECT SUM(b.amount) FROM budget b), 0) AS budget_cost,
    CASE WHEN COALESCE((SELECT SUM(b.amount) FROM budget b), 0) > 0
        THEN ((COALESCE(SUM(a.amount), 0) - (SELECT SUM(b.amount) FROM budget b))
              / (SELECT SUM(b.amount) FROM budget b)) * 100
        ELSE 0 END AS variance_pct,
    COALESCE(
        (SELECT SUM(amount) FILTER (WHERE entry_type = 'revenue') FROM actuals) * 100.0
        / NULLIF(
            (SELECT SUM(ABS(amount)) FROM actuals), 0
        ),
        0
    ) AS gross_margin_pct,
    CASE WHEN (SELECT COUNT(*) FROM actuals WHERE entry_type = 'cost' AND units > 0) > 0
        THEN (SELECT SUM(amount) / SUM(units) FROM actuals WHERE entry_type = 'cost' AND units > 0)
        ELSE NULL END AS unit_cost,
    COALESCE(SUM(a.amount) FILTER (WHERE a.entry_type = 'revenue'), 0) AS revenue
FROM actuals a
"""

_PARTICIPATION_QUERY = """
WITH week_bounds AS (
    SELECT %(week_start)s::date AS ws,
           (%(week_start)s::date + INTERVAL '7 days') AS we
),
activity AS (
    SELECT
        approver_email,
        COUNT(*) AS approvals
    FROM finance_ledger, week_bounds
    WHERE posting_date >= ws AND posting_date < we
      AND approver_email IS NOT NULL
      AND (%(cost_centers)s = '{}' OR cost_center = ANY(%(cost_centers)s))
    GROUP BY approver_email
)
SELECT
    p.person_id,
    0 AS tasks_owned,
    a.approvals AS tasks_contributed,
    a.approvals AS reviews_done,
    0 AS escalations_caused,
    0 AS blockers_caused,
    0 AS tasks_overdue_owned,
    'approver' AS role_in_process
FROM activity a
JOIN person_identities pi ON pi.identifier = a.approver_email AND pi.identity_type = 'email'
JOIN persons p ON p.person_id = pi.person_id
"""


class FinanceAdapter(BaseProcessAdapter):
    """Collects finance metrics from local ``finance_ledger`` / ``finance_budget`` mirrors."""

    def collect_metrics(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> dict[str, Any]:
        if not self._table_exists(conn, "finance_ledger"):
            logger.warning("process_collector.finance.no_table", table="finance_ledger")
            return {}

        cost_centers = self.query_config.get("cost_centers", [])

        rows = self._safe_query(
            conn,
            _METRICS_QUERY,
            {"week_start": week_start, "cost_centers": cost_centers},
        )
        if not rows:
            return {}

        mapped = self._apply_column_mapping(rows[0])
        logger.info(
            "process_collector.finance.collected",
            process_id=process_id,
            week_start=str(week_start),
        )
        return mapped

    def collect_participations(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> list[dict[str, Any]]:
        if not self._table_exists(conn, "finance_ledger"):
            return []

        cost_centers = self.query_config.get("cost_centers", [])

        rows = self._safe_query(
            conn,
            _PARTICIPATION_QUERY,
            {"week_start": week_start, "cost_centers": cost_centers},
        )
        logger.info(
            "process_collector.finance.participations",
            process_id=process_id,
            count=len(rows),
        )
        return rows
