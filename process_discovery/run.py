"""CLI entry point for process discovery."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import structlog

from app.db.postgres import get_pg_connection
from process_discovery.event_collectors import ALL_COLLECTORS
from process_discovery.llm_classifier import classify_candidates
from process_discovery.models import DiscoveryResult, ProcessEvent
from process_discovery.review_queue import (
    approve_candidate,
    auto_approve,
    list_pending,
    merge_candidates,
    reject_candidate,
)
from process_discovery.sequence_miner import mine_sequences, save_candidates

log = structlog.get_logger(__name__)


def run_migration() -> None:
    """Execute the SQL migration to create discovery tables."""
    migration_path = (
        Path(__file__).parent / "migrations" / "001_discovery_tables.sql"
    )
    sql = migration_path.read_text()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    log.info("migration_applied", file=str(migration_path))


def _save_events(events: list[ProcessEvent]) -> int:
    """Bulk insert process events into the database."""
    if not events:
        return 0

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            inserted = 0
            batch_size = 500
            for i in range(0, len(events), batch_size):
                batch = events[i : i + batch_size]
                values_parts = []
                params: list = []
                for ev in batch:
                    values_parts.append(
                        "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                    )
                    params.extend(
                        [
                            ev.source,
                            ev.entity_type,
                            ev.entity_id,
                            ev.from_state,
                            ev.to_state,
                            ev.state_group,
                            ev.actor_person_id,
                            ev.occurred_at,
                            ev.duration_in_prev_state_h,
                            ev.context_tags or [],
                            ev.project_key,
                            ev.priority,
                            ev.raw_data,
                        ]
                    )

                sql = f"""INSERT INTO process_events
                    (source, entity_type, entity_id, from_state, to_state,
                     state_group, actor_person_id, occurred_at,
                     duration_in_prev_state_h, context_tags, project_key,
                     priority, raw_data)
                    VALUES {', '.join(values_parts)}
                    ON CONFLICT DO NOTHING"""

                cur.execute(sql, params)
                inserted += cur.rowcount

        conn.commit()

    log.info("events_saved", count=inserted)
    return inserted


def run_discover(
    source_filter: str | None = None,
    since: datetime | None = None,
    min_occurrences: int = 10,
    min_per_week: float = 2.0,
) -> DiscoveryResult:
    """Full discovery pipeline: collect -> mine -> classify -> save."""
    result = DiscoveryResult()

    if since is None:
        since = datetime.now(timezone.utc) - timedelta(days=90)

    # Step 1: Collect events from all sources
    log.info("discovery_collect_start", source=source_filter, since=since.isoformat())

    all_events: list[ProcessEvent] = []

    with get_pg_connection() as conn:
        for CollectorClass in ALL_COLLECTORS:
            collector = CollectorClass()
            if source_filter and collector.source != source_filter:
                continue

            try:
                events = list(collector.collect_events(since, conn))
                all_events.extend(events)
                log.info(
                    "collector_done",
                    source=collector.source,
                    events=len(events),
                )
            except Exception as exc:
                log.error(
                    "collector_failed",
                    source=collector.source,
                    error=str(exc),
                )

    result.events_collected = len(all_events)

    # Save events to DB
    if all_events:
        _save_events(all_events)

    # Step 2: Mine sequences
    with get_pg_connection() as conn:
        candidates = mine_sequences(
            conn,
            source=source_filter,
            since=since,
            min_occurrences=min_occurrences,
            min_per_week=min_per_week,
        )

    result.sequences_found = len(candidates)

    if not candidates:
        log.info("discovery_no_candidates")
        return result

    # Step 3: Classify with LLM
    candidates = classify_candidates(candidates)

    # Step 4: Save candidates
    with get_pg_connection() as conn:
        new_count = save_candidates(conn, candidates)

    result.candidates_created = new_count

    log.info(
        "discovery_done",
        events=result.events_collected,
        sequences=result.sequences_found,
        candidates=result.candidates_created,
    )
    return result


def cmd_review_list() -> None:
    """Print pending candidates."""
    with get_pg_connection() as conn:
        pending = list_pending(conn)

    if not pending:
        print("No pending candidates.")
        return

    for c in pending:
        conf = c.get("llm_confidence")
        conf_str = f"{conf:.2f}" if conf is not None else "N/A"
        print(
            f"  {c['candidate_id']}  "
            f"[{c['source']}/{c['entity_type']}]  "
            f"{' -> '.join(c['sequence'])}  "
            f"({c['occurrences_count']}x, {c['occurrences_per_week']}/wk)  "
            f"conf={conf_str}  "
            f"name={c.get('suggested_name', '?')}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process Discovery — mine recurring business processes"
    )
    sub = parser.add_subparsers(dest="command")

    # discover
    disc = sub.add_parser("discover", help="Run full discovery pipeline")
    disc.add_argument("--source", help="Limit to one source (jira|crm|helpdesk|github|email)")
    disc.add_argument("--since", help="Start date (YYYY-MM-DD), default 90 days ago")
    disc.add_argument("--min-occurrences", type=int, default=10)
    disc.add_argument("--min-per-week", type=float, default=2.0)

    # review
    rev = sub.add_parser("review", help="Manage candidate review queue")
    rev.add_argument("--list", action="store_true", help="List pending candidates")
    rev.add_argument("--approve", metavar="ID", help="Approve a candidate")
    rev.add_argument("--reject", metavar="ID", help="Reject a candidate")
    rev.add_argument("--merge", nargs="+", metavar="ID", help="Merge candidates")
    rev.add_argument("--name", help="Name override for approve/merge")
    rev.add_argument("--reason", help="Rejection reason")
    rev.add_argument("--auto-approve", action="store_true", help="Auto-approve high-confidence")
    rev.add_argument("--min-confidence", type=float, default=0.9)

    # migrate
    sub.add_parser("migrate", help="Run SQL migration")

    # Also support --migrate at top level
    parser.add_argument("--migrate", action="store_true", help="Run SQL migration")

    args = parser.parse_args()

    if args.migrate:
        run_migration()
        return

    if args.command == "migrate":
        run_migration()

    elif args.command == "discover":
        since = None
        if args.since:
            since = datetime.strptime(args.since, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        result = run_discover(
            source_filter=args.source,
            since=since,
            min_occurrences=args.min_occurrences,
            min_per_week=args.min_per_week,
        )
        print(
            f"Discovery complete: "
            f"{result.events_collected} events, "
            f"{result.sequences_found} sequences, "
            f"{result.candidates_created} new candidates"
        )

    elif args.command == "review":
        if args.list:
            cmd_review_list()

        elif args.approve:
            cid = UUID(args.approve)
            with get_pg_connection() as conn:
                pid = approve_candidate(conn, cid, name_override=args.name)
            print(f"Approved {cid} -> process {pid}")

        elif args.reject:
            if not args.reason:
                print("Error: --reason is required for rejection", file=sys.stderr)
                sys.exit(1)
            cid = UUID(args.reject)
            with get_pg_connection() as conn:
                reject_candidate(conn, cid, args.reason)
            print(f"Rejected {cid}")

        elif args.merge:
            if not args.name:
                print("Error: --name is required for merge", file=sys.stderr)
                sys.exit(1)
            ids = [UUID(i) for i in args.merge]
            with get_pg_connection() as conn:
                pid = merge_candidates(conn, ids, args.name)
            print(f"Merged {len(ids)} candidates -> process {pid}")

        elif args.auto_approve:
            with get_pg_connection() as conn:
                count = auto_approve(conn, min_confidence=args.min_confidence)
            print(f"Auto-approved {count} candidates (threshold={args.min_confidence})")

        else:
            parser.parse_args(["review", "--help"])

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
