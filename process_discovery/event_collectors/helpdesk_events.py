"""Collect state-transition events from helpdesk ticket history."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import psycopg
import psycopg.rows
import structlog

from process_discovery.event_collectors.base import BaseEventCollector
from process_discovery.models import ProcessEvent

log = structlog.get_logger(__name__)


class HelpdeskEventCollector(BaseEventCollector):
    source = "helpdesk"
    entity_type = "ticket"

    def collect_events(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        if self._table_exists("helpdesk_ticket_history", conn):
            yield from self._from_history(since, conn)
        elif self._table_exists("helpdesk_tickets", conn):
            yield from self._from_tickets(since, conn)
        else:
            log.warning(
                "no helpdesk tables found "
                "(helpdesk_ticket_history, helpdesk_tickets), skipping"
            )

    def _from_history(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        query = """
            SELECT
                th.id,
                th.ticket_id,
                th.from_status AS from_state,
                th.to_status   AS to_state,
                th.changed_by,
                th.changed_at  AS occurred_at,
                LAG(th.changed_at) OVER (
                    PARTITION BY th.ticket_id ORDER BY th.changed_at
                ) AS prev_ts
            FROM helpdesk_ticket_history th
            WHERE th.changed_at >= %s
            ORDER BY th.ticket_id, th.changed_at
        """
        cursor_name = "helpdesk_history_cursor"
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

                    to_state = row.get("to_state", "")
                    actor_id = self._resolve_person(
                        row.get("changed_by", ""), conn
                    )

                    yield ProcessEvent(
                        source=self.source,
                        entity_type=self.entity_type,
                        entity_id=str(row["ticket_id"]),
                        from_state=row.get("from_state"),
                        to_state=to_state,
                        state_group=self.normalize_state(to_state),
                        actor_person_id=actor_id,
                        occurred_at=row["occurred_at"],
                        duration_in_prev_state_h=duration_h,
                        raw_data={"history_id": row.get("id")},
                    )

        log.info("helpdesk_history_collected", since=since.isoformat())

    def _from_tickets(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        """Fallback: one event per ticket from current status."""
        query = """
            SELECT
                ticket_id,
                status,
                assignee_email,
                updated_at,
                priority,
                category
            FROM helpdesk_tickets
            WHERE updated_at >= %s
            ORDER BY ticket_id
        """
        cursor_name = "helpdesk_tickets_cursor"
        with conn.cursor(name=cursor_name, row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, (since,))
            while True:
                rows = cur.fetchmany(2000)
                if not rows:
                    break
                for row in rows:
                    status = row.get("status", "")
                    actor_id = self._resolve_person(
                        row.get("assignee_email", ""), conn
                    )

                    yield ProcessEvent(
                        source=self.source,
                        entity_type=self.entity_type,
                        entity_id=str(row["ticket_id"]),
                        from_state=None,
                        to_state=status,
                        state_group=self.normalize_state(status),
                        actor_person_id=actor_id,
                        occurred_at=row.get("updated_at", since),
                        priority=row.get("priority"),
                        context_tags=[row["category"]] if row.get("category") else [],
                        raw_data={"fallback": True},
                    )

        log.info("helpdesk_tickets_fallback_collected", since=since.isoformat())
