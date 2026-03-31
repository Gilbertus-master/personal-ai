"""Abstract base for event collectors."""
from __future__ import annotations

import abc
from collections.abc import Iterator
from datetime import datetime
from typing import Optional
from uuid import UUID

import psycopg
import structlog

from process_discovery.models import ProcessEvent

log = structlog.get_logger(__name__)

# Canonical state groups — every raw state maps to one of these
STATE_NORMALIZATION: dict[str, str] = {
    # Jira
    "to do": "todo",
    "open": "todo",
    "backlog": "todo",
    "new": "todo",
    "in progress": "active",
    "in development": "active",
    "developing": "active",
    "in review": "review",
    "code review": "review",
    "review": "review",
    "done": "done",
    "closed": "done",
    "resolved": "done",
    "blocked": "blocked",
    "on hold": "blocked",
    "waiting": "blocked",
    "cancelled": "cancelled",
    "won't do": "cancelled",
    "wontfix": "cancelled",
    "duplicate": "cancelled",
    # CRM
    "new lead": "todo",
    "qualified": "active",
    "contacted": "active",
    "proposal": "active",
    "negotiation": "review",
    "contract sent": "review",
    "closed won": "done",
    "closed lost": "cancelled",
    "lost": "cancelled",
    # Helpdesk
    "pending": "blocked",
    "waiting on customer": "blocked",
    "waiting on third party": "blocked",
    "solved": "done",
    "escalated": "review",
    # GitHub
    "opened": "todo",
    "draft": "todo",
    "review_requested": "review",
    "changes_requested": "active",
    "approved": "review",
    "merged": "done",
}


class BaseEventCollector(abc.ABC):
    """Abstract collector that reads events from a source system."""

    source: str = ""
    entity_type: str = ""

    def normalize_state(self, raw_state: str) -> str:
        """Map a raw state string to a canonical state_group."""
        if raw_state is None:
            return "todo"
        key = raw_state.strip().lower()
        return STATE_NORMALIZATION.get(key, key)

    def _resolve_person(
        self, identifier: str, conn: psycopg.Connection
    ) -> Optional[UUID]:
        """Look up a person by email, username, or display name."""
        if not identifier:
            return None
        with conn.cursor() as cur:
            cur.execute(
                """SELECT person_id FROM person_identities
                   WHERE LOWER(identity_value) = LOWER(%s)
                   LIMIT 1""",
                (identifier,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    def _table_exists(self, table_name: str, conn: psycopg.Connection) -> bool:
        """Check if a table exists in the database."""
        with conn.cursor() as cur:
            cur.execute(
                """SELECT EXISTS (
                       SELECT 1 FROM information_schema.tables
                       WHERE table_name = %s AND table_schema = 'public'
                   )""",
                (table_name,),
            )
            row = cur.fetchone()
            return bool(row and row[0])

    @abc.abstractmethod
    def collect_events(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        """Yield ProcessEvent objects from this source since the given time."""
        ...
