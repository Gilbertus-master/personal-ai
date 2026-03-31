"""Collect state-transition events from CRM deal history."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import psycopg
import psycopg.rows
import structlog

from process_discovery.event_collectors.base import BaseEventCollector
from process_discovery.models import ProcessEvent

log = structlog.get_logger(__name__)


class CrmEventCollector(BaseEventCollector):
    source = "crm"
    entity_type = "deal"

    def collect_events(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        # Try deal_history first (richer), fall back to deals table
        if self._table_exists("crm_deal_history", conn):
            yield from self._from_deal_history(since, conn)
        elif self._table_exists("crm_deals", conn):
            yield from self._from_deals_table(since, conn)
        else:
            log.warning("no CRM tables found (crm_deal_history, crm_deals), skipping")

    def _from_deal_history(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        query = """
            SELECT
                dh.id,
                dh.deal_id,
                dh.from_stage  AS from_state,
                dh.to_stage    AS to_state,
                dh.changed_by,
                dh.changed_at  AS occurred_at,
                LAG(dh.changed_at) OVER (
                    PARTITION BY dh.deal_id ORDER BY dh.changed_at
                ) AS prev_ts,
                dh.deal_id     AS entity_id_raw
            FROM crm_deal_history dh
            WHERE dh.changed_at >= %s
            ORDER BY dh.deal_id, dh.changed_at
        """
        cursor_name = "crm_history_cursor"
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
                        entity_id=str(row.get("deal_id", row.get("entity_id_raw", ""))),
                        from_state=row.get("from_state"),
                        to_state=to_state,
                        state_group=self.normalize_state(to_state),
                        actor_person_id=actor_id,
                        occurred_at=row["occurred_at"],
                        duration_in_prev_state_h=duration_h,
                        raw_data={"history_id": row.get("id")},
                    )

        log.info("crm_deal_history_collected", since=since.isoformat())

    def _from_deals_table(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        """Fallback: generate a single event per deal from current stage."""
        query = """
            SELECT
                deal_id,
                stage,
                owner_email,
                updated_at,
                pipeline
            FROM crm_deals
            WHERE updated_at >= %s
            ORDER BY deal_id
        """
        cursor_name = "crm_deals_cursor"
        with conn.cursor(name=cursor_name, row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, (since,))
            while True:
                rows = cur.fetchmany(2000)
                if not rows:
                    break
                for row in rows:
                    stage = row.get("stage", "")
                    actor_id = self._resolve_person(
                        row.get("owner_email", ""), conn
                    )

                    yield ProcessEvent(
                        source=self.source,
                        entity_type=self.entity_type,
                        entity_id=str(row["deal_id"]),
                        from_state=None,
                        to_state=stage,
                        state_group=self.normalize_state(stage),
                        actor_person_id=actor_id,
                        occurred_at=row.get("updated_at", since),
                        project_key=row.get("pipeline"),
                        raw_data={"fallback": True},
                    )

        log.info("crm_deals_fallback_collected", since=since.isoformat())
