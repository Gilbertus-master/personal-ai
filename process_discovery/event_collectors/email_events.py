"""Collect state-transition events from email threads (heuristic-based)."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import psycopg
import psycopg.rows
import structlog

from process_discovery.event_collectors.base import BaseEventCollector
from process_discovery.models import ProcessEvent

log = structlog.get_logger(__name__)


class EmailEventCollector(BaseEventCollector):
    source = "email"
    entity_type = "email_thread"

    def collect_events(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        # Try chunks table with email source as the common storage
        if not self._table_exists("chunks", conn):
            log.warning("chunks table not found, skipping email events")
            return

        # Check if there are email-sourced chunks with conversation_id
        with conn.cursor() as cur:
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM chunks
                       WHERE source_type IN ('email', 'outlook', 'graph_email')
                       LIMIT 1
                   )"""
            )
            row = cur.fetchone()
            if not row or not row[0]:
                log.warning("no email chunks found, skipping")
                return

        yield from self._from_email_chunks(since, conn)

    def _from_email_chunks(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        """
        Heuristic: group emails by conversation_id (or subject thread).
        Detect lifecycle: new_thread -> reply -> resolution.
        Resolution heuristic: thread with no reply for 48h+ after last message.
        """
        query = """
            WITH email_threads AS (
                SELECT
                    COALESCE(metadata->>'conversation_id',
                             metadata->>'thread_id',
                             MD5(LOWER(REGEXP_REPLACE(
                                 COALESCE(metadata->>'subject', ''),
                                 '^(Re:|Fwd:|FW:|RE:)\\s*', '', 'gi'
                             )))
                    ) AS thread_id,
                    c.id AS chunk_id,
                    COALESCE(metadata->>'from_email',
                             metadata->>'sender') AS sender,
                    c.imported_at AS occurred_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY COALESCE(
                            metadata->>'conversation_id',
                            metadata->>'thread_id',
                            MD5(LOWER(REGEXP_REPLACE(
                                COALESCE(metadata->>'subject', ''),
                                '^(Re:|Fwd:|FW:|RE:)\\s*', '', 'gi'
                            )))
                        )
                        ORDER BY c.imported_at
                    ) AS msg_seq,
                    COALESCE(metadata->>'subject', '') AS subject
                FROM chunks c
                WHERE c.source_type IN ('email', 'outlook', 'graph_email')
                  AND c.imported_at >= %s
            )
            SELECT
                thread_id,
                chunk_id,
                sender,
                occurred_at,
                msg_seq,
                subject,
                LAG(occurred_at) OVER (
                    PARTITION BY thread_id ORDER BY occurred_at
                ) AS prev_ts
            FROM email_threads
            ORDER BY thread_id, occurred_at
        """
        cursor_name = "email_threads_cursor"
        with conn.cursor(name=cursor_name, row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, (since,))
            while True:
                rows = cur.fetchmany(2000)
                if not rows:
                    break
                for row in rows:
                    thread_id = row["thread_id"]
                    msg_seq = row.get("msg_seq", 1)

                    # Determine state based on position in thread
                    if msg_seq == 1:
                        from_state = None
                        to_state = "new_thread"
                        state_group = "todo"
                    elif msg_seq == 2:
                        from_state = "new_thread"
                        to_state = "first_reply"
                        state_group = "active"
                    else:
                        from_state = "active"
                        to_state = "follow_up"
                        state_group = "active"

                    duration_h = None
                    if row.get("prev_ts") and row.get("occurred_at"):
                        delta = row["occurred_at"] - row["prev_ts"]
                        duration_h = delta.total_seconds() / 3600.0

                        # Heuristic: if >48h gap after a reply, treat as resolved
                        if duration_h > 48 and msg_seq > 1:
                            to_state = "resolved"
                            state_group = "done"

                    actor_id = self._resolve_person(
                        row.get("sender", ""), conn
                    )

                    yield ProcessEvent(
                        source=self.source,
                        entity_type=self.entity_type,
                        entity_id=str(thread_id),
                        from_state=from_state,
                        to_state=to_state,
                        state_group=state_group,
                        actor_person_id=actor_id,
                        occurred_at=row["occurred_at"],
                        duration_in_prev_state_h=duration_h,
                        context_tags=self._extract_tags(row.get("subject", "")),
                        raw_data={"chunk_id": str(row.get("chunk_id", ""))},
                    )

        log.info("email_events_collected", since=since.isoformat())

    @staticmethod
    def _extract_tags(subject: str) -> list[str]:
        """Extract simple context tags from email subject."""
        tags: list[str] = []
        lower = subject.lower()
        tag_keywords = {
            "urgent": "urgent",
            "pilne": "urgent",
            "faktura": "invoice",
            "invoice": "invoice",
            "umowa": "contract",
            "contract": "contract",
            "meeting": "meeting",
            "spotkanie": "meeting",
            "raport": "report",
            "report": "report",
        }
        for keyword, tag in tag_keywords.items():
            if keyword in lower and tag not in tags:
                tags.append(tag)
        return tags
