"""Jira adapter — collects sprint/kanban metrics from a local Jira mirror table."""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg
import structlog

from process_collector.adapters.base import BaseProcessAdapter

logger = structlog.get_logger(__name__)

# Expected local mirror table: jira_issues
# Columns: issue_key, project_key, issue_type, status, story_points,
#           created_at, resolved_at, updated_at, assignee_email, sprint_id,
#           is_blocked, is_blocker, reopen_count
_METRICS_QUERY = """
WITH week_bounds AS (
    SELECT %(week_start)s::date AS ws,
           (%(week_start)s::date + INTERVAL '7 days') AS we
),
resolved AS (
    SELECT *
    FROM jira_issues, week_bounds
    WHERE resolved_at >= ws AND resolved_at < we
      AND (%(project_keys)s = '{}' OR project_key = ANY(%(project_keys)s))
      AND issue_type = ANY(%(issue_types)s)
),
in_progress AS (
    SELECT *
    FROM jira_issues, week_bounds
    WHERE status IN ('In Progress', 'In Review', 'In QA')
      AND (%(project_keys)s = '{}' OR project_key = ANY(%(project_keys)s))
),
overdue AS (
    SELECT *
    FROM jira_issues, week_bounds
    WHERE status NOT IN ('Done', 'Closed', 'Resolved')
      AND created_at < (ws - INTERVAL '14 days')
      AND (%(project_keys)s = '{}' OR project_key = ANY(%(project_keys)s))
)
SELECT
    (SELECT COUNT(*) FROM resolved) AS issues_completed,
    (SELECT COALESCE(SUM(story_points), 0) FROM resolved) AS story_points_completed,
    (SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600.0) FROM resolved) AS avg_cycle_time_hours,
    (SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (
        ORDER BY EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600.0
    ) FROM resolved) AS p90_cycle_time_hours,
    (SELECT COUNT(*) FROM overdue) AS overdue_issues,
    (SELECT COUNT(*) FROM in_progress) AS issues_in_progress,
    (SELECT COUNT(*) FROM resolved WHERE issue_type = 'Bug') AS bugs_created,
    (SELECT COUNT(*) FROM in_progress WHERE is_blocked) AS blockers_active,
    (SELECT CASE WHEN COUNT(*) > 0
        THEN COUNT(*) FILTER (WHERE reopen_count > 0)::float / COUNT(*)
        ELSE 0 END FROM resolved) AS reopened_rate
"""

_PARTICIPATION_QUERY = """
WITH week_bounds AS (
    SELECT %(week_start)s::date AS ws,
           (%(week_start)s::date + INTERVAL '7 days') AS we
),
activity AS (
    SELECT
        assignee_email,
        COUNT(*) FILTER (WHERE resolved_at >= ws AND resolved_at < we) AS resolved,
        COUNT(*) FILTER (WHERE status IN ('In Progress','In Review','In QA')) AS contributed,
        COUNT(*) FILTER (WHERE is_blocker) AS blockers,
        COUNT(*) FILTER (WHERE resolved_at IS NULL AND created_at < ws - INTERVAL '14 days') AS overdue
    FROM jira_issues, week_bounds
    WHERE (%(project_keys)s = '{}' OR project_key = ANY(%(project_keys)s))
      AND (
          (resolved_at >= ws AND resolved_at < we)
          OR status IN ('In Progress','In Review','In QA')
      )
    GROUP BY assignee_email
)
SELECT
    p.person_id,
    a.resolved AS tasks_owned,
    a.contributed AS tasks_contributed,
    0 AS reviews_done,
    0 AS escalations_caused,
    a.blockers AS blockers_caused,
    a.overdue AS tasks_overdue_owned,
    CASE WHEN a.resolved > 0 THEN 'owner' ELSE 'contributor' END AS role_in_process
FROM activity a
JOIN person_identities pi ON pi.identifier = a.assignee_email AND pi.identity_type = 'email'
JOIN persons p ON p.person_id = pi.person_id
WHERE a.assignee_email IS NOT NULL
"""


class JiraAdapter(BaseProcessAdapter):
    """Collects sprint/kanban metrics from a local ``jira_issues`` mirror."""

    def collect_metrics(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> dict[str, Any]:
        if not self._table_exists(conn, "jira_issues"):
            logger.warning("process_collector.jira.no_table", table="jira_issues")
            return {}

        project_keys = self.query_config.get("project_keys", [])
        issue_types = self.query_config.get("issue_types", ["Story", "Bug", "Task"])

        rows = self._safe_query(
            conn,
            _METRICS_QUERY,
            {
                "week_start": week_start,
                "project_keys": project_keys,
                "issue_types": issue_types,
            },
        )
        if not rows:
            return {}

        raw = rows[0]
        mapped = self._apply_column_mapping(raw)
        logger.info(
            "process_collector.jira.collected",
            process_id=process_id,
            week_start=str(week_start),
            metrics_count=len([v for v in mapped.values() if v is not None]),
        )
        return mapped

    def collect_participations(
        self,
        process_id: str,
        week_start: date,
        conn: psycopg.Connection,
    ) -> list[dict[str, Any]]:
        if not self._table_exists(conn, "jira_issues"):
            return []

        project_keys = self.query_config.get("project_keys", [])

        rows = self._safe_query(
            conn,
            _PARTICIPATION_QUERY,
            {
                "week_start": week_start,
                "project_keys": project_keys,
            },
        )
        logger.info(
            "process_collector.jira.participations",
            process_id=process_id,
            count=len(rows),
        )
        return rows
