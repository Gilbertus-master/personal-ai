"""Helpdesk adapter — collects customer service metrics from a local mirror."""

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
created AS (
    SELECT * FROM helpdesk_tickets, week_bounds
    WHERE created_at >= ws AND created_at < we
      AND (%(queue_ids)s = '{}' OR queue_id = ANY(%(queue_ids)s))
),
resolved AS (
    SELECT * FROM helpdesk_tickets, week_bounds
    WHERE resolved_at >= ws AND resolved_at < we
      AND (%(queue_ids)s = '{}' OR queue_id = ANY(%(queue_ids)s))
)
SELECT
    (SELECT COUNT(*) FROM resolved) AS resolved_count,
    (SELECT AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 3600.0)
     FROM resolved WHERE first_response_at IS NOT NULL) AS avg_first_response_hours,
    (SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600.0)
     FROM resolved) AS avg_resolution_hours,
    (SELECT CASE WHEN COUNT(*) > 0
        THEN COUNT(*) FILTER (WHERE escalated)::float / COUNT(*)
        ELSE 0 END FROM resolved) AS escalation_pct,
    (SELECT AVG(csat_rating) FROM resolved WHERE csat_rating IS NOT NULL) AS csat_avg,
    (SELECT AVG(nps_rating) FROM resolved WHERE nps_rating IS NOT NULL) AS nps_avg,
    (SELECT CASE WHEN COUNT(*) > 0
        THEN COUNT(*) FILTER (WHERE touch_count = 1)::float / COUNT(*)
        ELSE 0 END FROM resolved) AS fcr_rate,
    (SELECT COUNT(*) FROM created) AS tickets_created,
    (SELECT COUNT(*) FROM resolved WHERE sla_breached) AS sla_breaches
"""

_PARTICIPATION_QUERY = """
WITH week_bounds AS (
    SELECT %(week_start)s::date AS ws,
           (%(week_start)s::date + INTERVAL '7 days') AS we
),
activity AS (
    SELECT
        agent_email,
        COUNT(*) FILTER (WHERE resolved_at >= ws AND resolved_at < we) AS resolved,
        COUNT(*) FILTER (WHERE escalated) AS escalations,
        COUNT(*) FILTER (WHERE sla_breached) AS overdue,
        AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 3600.0)
            FILTER (WHERE first_response_at IS NOT NULL) AS avg_resp_h
    FROM helpdesk_tickets, week_bounds
    WHERE (resolved_at >= ws AND resolved_at < we)
      AND (%(queue_ids)s = '{}' OR queue_id = ANY(%(queue_ids)s))
    GROUP BY agent_email
)
SELECT
    p.person_id,
    a.resolved AS tasks_owned,
    a.resolved AS tasks_contributed,
    0 AS reviews_done,
    a.escalations AS escalations_caused,
    0 AS blockers_caused,
    a.overdue AS tasks_overdue_owned,
    a.avg_resp_h AS avg_response_time_h,
    'executor' AS role_in_process
FROM activity a
JOIN person_identities pi ON pi.identifier = a.agent_email AND pi.identity_type = 'email'
JOIN persons p ON p.person_id = pi.person_id
"""


class HelpdeskAdapter(BaseProcessAdapter):
    """Collects customer-service metrics from a local ``helpdesk_tickets`` mirror."""

    def collect_metrics(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> dict[str, Any]:
        if not self._table_exists(conn, "helpdesk_tickets"):
            logger.warning("process_collector.helpdesk.no_table", table="helpdesk_tickets")
            return {}

        queue_ids = self.query_config.get("queue_ids", [])

        rows = self._safe_query(
            conn,
            _METRICS_QUERY,
            {"week_start": week_start, "queue_ids": queue_ids},
        )
        if not rows:
            return {}

        mapped = self._apply_column_mapping(rows[0])
        logger.info(
            "process_collector.helpdesk.collected",
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
        if not self._table_exists(conn, "helpdesk_tickets"):
            return []

        queue_ids = self.query_config.get("queue_ids", [])

        rows = self._safe_query(
            conn,
            _PARTICIPATION_QUERY,
            {"week_start": week_start, "queue_ids": queue_ids},
        )
        logger.info(
            "process_collector.helpdesk.participations",
            process_id=process_id,
            count=len(rows),
        )
        return rows
