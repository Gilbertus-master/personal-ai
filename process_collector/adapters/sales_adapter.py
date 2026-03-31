"""Sales / CRM adapter — collects pipeline metrics from a local CRM mirror table."""

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
closed AS (
    SELECT * FROM crm_deals, week_bounds
    WHERE closed_at >= ws AND closed_at < we
      AND (%(pipeline_ids)s = '{}' OR pipeline_id = ANY(%(pipeline_ids)s))
),
pipeline AS (
    SELECT * FROM crm_deals
    WHERE status = 'open'
      AND (%(pipeline_ids)s = '{}' OR pipeline_id = ANY(%(pipeline_ids)s))
)
SELECT
    COALESCE(SUM(CASE WHEN c.status = 'won' THEN c.value_pln ELSE 0 END), 0) AS total_revenue,
    COUNT(*) FILTER (WHERE c.status = 'won') AS deals_won,
    COUNT(*) FILTER (WHERE c.status = 'lost') AS deals_lost,
    CASE WHEN COUNT(*) > 0
        THEN COUNT(*) FILTER (WHERE c.status = 'won')::float / COUNT(*)
        ELSE 0 END AS win_rate,
    CASE WHEN COUNT(*) FILTER (WHERE c.status = 'won') > 0
        THEN AVG(c.value_pln) FILTER (WHERE c.status = 'won')
        ELSE 0 END AS avg_deal_value,
    AVG(EXTRACT(DAY FROM (c.closed_at - c.created_at))) FILTER (WHERE c.status = 'won') AS avg_cycle_days,
    (SELECT COALESCE(SUM(value_pln), 0) FROM pipeline) AS pipeline_total,
    (SELECT COUNT(*) FROM closed) AS total_activities
FROM closed c
"""

_PARTICIPATION_QUERY = """
WITH week_bounds AS (
    SELECT %(week_start)s::date AS ws,
           (%(week_start)s::date + INTERVAL '7 days') AS we
),
activity AS (
    SELECT
        owner_email,
        COUNT(*) FILTER (WHERE status = 'won') AS won,
        COUNT(*) FILTER (WHERE status = 'lost') AS lost,
        COUNT(*) AS total
    FROM crm_deals, week_bounds
    WHERE closed_at >= ws AND closed_at < we
      AND (%(pipeline_ids)s = '{}' OR pipeline_id = ANY(%(pipeline_ids)s))
    GROUP BY owner_email
)
SELECT
    p.person_id,
    a.won AS tasks_owned,
    a.total AS tasks_contributed,
    0 AS reviews_done,
    0 AS escalations_caused,
    0 AS blockers_caused,
    a.lost AS tasks_overdue_owned,
    'owner' AS role_in_process
FROM activity a
JOIN person_identities pi ON pi.identifier = a.owner_email AND pi.identity_type = 'email'
JOIN persons p ON p.person_id = pi.person_id
"""


class SalesAdapter(BaseProcessAdapter):
    """Collects sales pipeline metrics from a local ``crm_deals`` mirror."""

    def collect_metrics(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> dict[str, Any]:
        if not self._table_exists(conn, "crm_deals"):
            logger.warning("process_collector.sales.no_table", table="crm_deals")
            return {}

        pipeline_ids = self.query_config.get("pipeline_ids", [])

        rows = self._safe_query(
            conn,
            _METRICS_QUERY,
            {"week_start": week_start, "pipeline_ids": pipeline_ids},
        )
        if not rows:
            return {}

        mapped = self._apply_column_mapping(rows[0])
        logger.info(
            "process_collector.sales.collected",
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
        if not self._table_exists(conn, "crm_deals"):
            return []

        pipeline_ids = self.query_config.get("pipeline_ids", [])

        rows = self._safe_query(
            conn,
            _PARTICIPATION_QUERY,
            {"week_start": week_start, "pipeline_ids": pipeline_ids},
        )
        logger.info(
            "process_collector.sales.participations",
            process_id=process_id,
            count=len(rows),
        )
        return rows
