"""Collect state-transition events from Jira changelog."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import psycopg
import psycopg.rows
import structlog

from process_discovery.event_collectors.base import BaseEventCollector
from process_discovery.models import ProcessEvent

log = structlog.get_logger(__name__)


class JiraEventCollector(BaseEventCollector):
    source = "jira"
    entity_type = "ticket"

    def collect_events(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        if not self._table_exists("jira_changelog", conn):
            log.warning("jira_changelog table not found, skipping")
            return

        has_issues = self._table_exists("jira_issues", conn)

        query = """
            SELECT
                cl.id,
                cl.issue_key,
                cl.field,
                cl.from_string AS from_state,
                cl.to_string   AS to_state,
                cl.author_email,
                cl.created_at  AS occurred_at,
                LAG(cl.created_at) OVER (
                    PARTITION BY cl.issue_key
                    ORDER BY cl.created_at
                ) AS prev_ts
        """
        if has_issues:
            query += """,
                ji.project_key,
                ji.priority
            FROM jira_changelog cl
            LEFT JOIN jira_issues ji ON ji.issue_key = cl.issue_key
            """
        else:
            query += """,
                SPLIT_PART(cl.issue_key, '-', 1) AS project_key,
                NULL AS priority
            FROM jira_changelog cl
            """

        query += """
            WHERE cl.field = 'status'
              AND cl.created_at >= %s
            ORDER BY cl.issue_key, cl.created_at
        """

        cursor_name = "jira_events_cursor"
        with conn.cursor(name=cursor_name, row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, (since,))
            while True:
                rows = cur.fetchmany(2000)
                if not rows:
                    break
                for row in rows:
                    duration_h = None
                    if row.get("prev_ts") and row.get("occurred_at"):
                        delta = row["occurred_at"] - row["prev_ts"]
                        duration_h = delta.total_seconds() / 3600.0

                    from_state = row.get("from_state")
                    to_state = row.get("to_state", "")
                    actor_id = self._resolve_person(
                        row.get("author_email", ""), conn
                    )

                    yield ProcessEvent(
                        source=self.source,
                        entity_type=self.entity_type,
                        entity_id=row["issue_key"],
                        from_state=from_state,
                        to_state=to_state,
                        state_group=self.normalize_state(to_state),
                        actor_person_id=actor_id,
                        occurred_at=row["occurred_at"],
                        duration_in_prev_state_h=duration_h,
                        project_key=row.get("project_key"),
                        priority=row.get("priority"),
                        raw_data={
                            "changelog_id": row.get("id"),
                            "field": "status",
                        },
                    )

        log.info("jira_events_collected", since=since.isoformat())
