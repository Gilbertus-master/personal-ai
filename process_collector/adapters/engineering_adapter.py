"""Engineering / CI-CD adapter — collects DORA-style metrics from a local mirror."""

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
deploys AS (
    SELECT * FROM cicd_deployments, week_bounds
    WHERE deployed_at >= ws AND deployed_at < we
      AND (%(repos)s = '{}' OR repo = ANY(%(repos)s))
      AND (%(environments)s = '{}' OR environment = ANY(%(environments)s))
),
prs AS (
    SELECT * FROM cicd_pull_requests, week_bounds
    WHERE merged_at >= ws AND merged_at < we
      AND (%(repos)s = '{}' OR repo = ANY(%(repos)s))
),
bugs AS (
    SELECT * FROM cicd_bugs
    WHERE severity = 'critical' AND status NOT IN ('Done','Closed','Resolved')
      AND (%(repos)s = '{}' OR repo = ANY(%(repos)s))
)
SELECT
    (SELECT COUNT(*) FROM deploys) AS total_deployments,
    (SELECT COUNT(*) FROM deploys WHERE status = 'failed') AS failed_deployments,
    (SELECT CASE WHEN COUNT(*) > 0
        THEN COUNT(*) FILTER (WHERE status = 'failed')::float / COUNT(*)
        ELSE 0 END FROM deploys) AS failure_rate_pct,
    (SELECT AVG(EXTRACT(EPOCH FROM (restored_at - failed_at)) / 3600.0)
     FROM deploys WHERE status = 'failed' AND restored_at IS NOT NULL) AS mean_time_to_restore_h,
    (SELECT MAX(coverage_pct) FROM deploys WHERE coverage_pct IS NOT NULL) AS coverage_pct,
    (SELECT COUNT(*) FROM bugs) AS critical_open,
    (SELECT COALESCE(SUM(debt_hours), 0) FROM deploys WHERE debt_hours IS NOT NULL) AS debt_estimate_hours,
    (SELECT COUNT(*) FROM prs) AS prs_merged,
    (SELECT AVG(EXTRACT(EPOCH FROM (merged_at - created_at)) / 3600.0) FROM prs) AS avg_pr_cycle_hours
"""

_PARTICIPATION_QUERY = """
WITH week_bounds AS (
    SELECT %(week_start)s::date AS ws,
           (%(week_start)s::date + INTERVAL '7 days') AS we
),
activity AS (
    SELECT
        author_email,
        COUNT(*) AS prs_merged,
        COUNT(*) FILTER (WHERE reviews_given > 0) AS reviews
    FROM cicd_pull_requests, week_bounds
    WHERE merged_at >= ws AND merged_at < we
      AND (%(repos)s = '{}' OR repo = ANY(%(repos)s))
    GROUP BY author_email
)
SELECT
    p.person_id,
    a.prs_merged AS tasks_owned,
    a.prs_merged AS tasks_contributed,
    a.reviews AS reviews_done,
    0 AS escalations_caused,
    0 AS blockers_caused,
    0 AS tasks_overdue_owned,
    'contributor' AS role_in_process
FROM activity a
JOIN person_identities pi ON pi.identifier = a.author_email AND pi.identity_type = 'email'
JOIN persons p ON p.person_id = pi.person_id
"""


class EngineeringAdapter(BaseProcessAdapter):
    """Collects CI/CD and DORA metrics from local mirror tables."""

    def collect_metrics(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> dict[str, Any]:
        # Need at least the deployments table
        if not self._table_exists(conn, "cicd_deployments"):
            logger.warning("process_collector.engineering.no_table", table="cicd_deployments")
            return {}

        repos = self.query_config.get("repos", [])
        environments = self.query_config.get("environments", [])

        rows = self._safe_query(
            conn,
            _METRICS_QUERY,
            {"week_start": week_start, "repos": repos, "environments": environments},
        )
        if not rows:
            return {}

        mapped = self._apply_column_mapping(rows[0])
        logger.info(
            "process_collector.engineering.collected",
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
        if not self._table_exists(conn, "cicd_pull_requests"):
            return []

        repos = self.query_config.get("repos", [])

        rows = self._safe_query(
            conn,
            _PARTICIPATION_QUERY,
            {"week_start": week_start, "repos": repos},
        )
        logger.info(
            "process_collector.engineering.participations",
            process_id=process_id,
            count=len(rows),
        )
        return rows
