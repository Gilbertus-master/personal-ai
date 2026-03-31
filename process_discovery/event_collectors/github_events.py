"""Collect state-transition events from GitHub PR lifecycle."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import psycopg
import psycopg.rows
import structlog

from process_discovery.event_collectors.base import BaseEventCollector
from process_discovery.models import ProcessEvent

log = structlog.get_logger(__name__)


class GithubEventCollector(BaseEventCollector):
    source = "github"
    entity_type = "pr"

    def collect_events(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        if self._table_exists("github_pr_events", conn):
            yield from self._from_pr_events(since, conn)
        elif self._table_exists("github_pull_requests", conn):
            yield from self._from_pull_requests(since, conn)
        else:
            log.warning(
                "no GitHub tables found "
                "(github_pr_events, github_pull_requests), skipping"
            )

    def _from_pr_events(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        query = """
            SELECT
                pe.id,
                pe.pr_number,
                pe.repo,
                pe.event_type  AS to_state,
                pe.actor,
                pe.created_at  AS occurred_at,
                LAG(pe.event_type) OVER (
                    PARTITION BY pe.repo, pe.pr_number ORDER BY pe.created_at
                ) AS from_state,
                LAG(pe.created_at) OVER (
                    PARTITION BY pe.repo, pe.pr_number ORDER BY pe.created_at
                ) AS prev_ts
            FROM github_pr_events pe
            WHERE pe.created_at >= %s
            ORDER BY pe.repo, pe.pr_number, pe.created_at
        """
        cursor_name = "github_events_cursor"
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
                        row.get("actor", ""), conn
                    )
                    repo = row.get("repo", "")
                    entity_id = f"{repo}#{row.get('pr_number', '')}"

                    yield ProcessEvent(
                        source=self.source,
                        entity_type=self.entity_type,
                        entity_id=entity_id,
                        from_state=row.get("from_state"),
                        to_state=to_state,
                        state_group=self.normalize_state(to_state),
                        actor_person_id=actor_id,
                        occurred_at=row["occurred_at"],
                        duration_in_prev_state_h=duration_h,
                        project_key=repo,
                        raw_data={"event_id": row.get("id")},
                    )

        log.info("github_pr_events_collected", since=since.isoformat())

    def _from_pull_requests(
        self, since: datetime, conn: psycopg.Connection
    ) -> Iterator[ProcessEvent]:
        """Fallback: synthesize events from PR state snapshots."""
        query = """
            SELECT
                pr_number,
                repo,
                state,
                author,
                updated_at,
                merged_at,
                closed_at,
                created_at AS pr_created_at
            FROM github_pull_requests
            WHERE updated_at >= %s
            ORDER BY repo, pr_number
        """
        cursor_name = "github_prs_cursor"
        with conn.cursor(name=cursor_name, row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, (since,))
            while True:
                rows = cur.fetchmany(2000)
                if not rows:
                    break
                for row in rows:
                    repo = row.get("repo", "")
                    entity_id = f"{repo}#{row.get('pr_number', '')}"
                    actor_id = self._resolve_person(
                        row.get("author", ""), conn
                    )

                    # Created event
                    yield ProcessEvent(
                        source=self.source,
                        entity_type=self.entity_type,
                        entity_id=entity_id,
                        from_state=None,
                        to_state="opened",
                        state_group="todo",
                        actor_person_id=actor_id,
                        occurred_at=row["pr_created_at"],
                        project_key=repo,
                        raw_data={"fallback": True},
                    )

                    # Terminal event
                    if row.get("merged_at"):
                        yield ProcessEvent(
                            source=self.source,
                            entity_type=self.entity_type,
                            entity_id=entity_id,
                            from_state="opened",
                            to_state="merged",
                            state_group="done",
                            actor_person_id=actor_id,
                            occurred_at=row["merged_at"],
                            project_key=repo,
                            raw_data={"fallback": True},
                        )
                    elif row.get("closed_at"):
                        yield ProcessEvent(
                            source=self.source,
                            entity_type=self.entity_type,
                            entity_id=entity_id,
                            from_state="opened",
                            to_state="closed",
                            state_group="cancelled",
                            actor_person_id=actor_id,
                            occurred_at=row["closed_at"],
                            project_key=repo,
                            raw_data={"fallback": True},
                        )

        log.info("github_pull_requests_fallback_collected", since=since.isoformat())
