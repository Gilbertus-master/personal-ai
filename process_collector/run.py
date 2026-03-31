"""CLI entry point: python -m process_collector.run"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def _run_migration(conn) -> None:
    """Execute the SQL migration file."""
    migration_path = Path(__file__).parent / "migrations" / "001_process_tables.sql"
    if not migration_path.exists():
        logger.error("process_collector.run.migration_missing", path=str(migration_path))
        sys.exit(1)

    sql = migration_path.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
    # The migration file contains its own BEGIN/COMMIT
    logger.info("process_collector.run.migration_applied", path=str(migration_path))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="process_collector",
        description="Collect process-level metrics from business systems into weekly aggregates.",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Collect only this source (by name from process_sources.yaml). Default: all enabled.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect metrics but do not persist to database.",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Run the SQL migration to create/update process tables.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to process_sources.yaml config file.",
    )
    parser.add_argument(
        "--week-start",
        type=str,
        default=None,
        help="Override week start date (YYYY-MM-DD). Default: current Monday.",
    )

    args = parser.parse_args()

    # Import here to avoid circular / heavy imports at parse time
    from app.db.postgres import get_pg_connection
    from process_collector.pipeline import run_collection

    with get_pg_connection() as conn:
        # Migration
        if args.migrate:
            _run_migration(conn)
            if not args.source and not args.dry_run and not args.week_start:
                # Only migrate was requested
                logger.info("process_collector.run.migration_only")
                return

        # Parse optional week_start
        week_start = None
        if args.week_start:
            from datetime import date as _date
            week_start = _date.fromisoformat(args.week_start)

        # Source filter
        source_names = [args.source] if args.source else None

        # Run
        results = run_collection(
            conn,
            source_names=source_names,
            config_path=args.config,
            dry_run=args.dry_run,
            week_start=week_start,
        )

        # Summary
        total_metrics = sum(r.metrics_collected for r in results)
        total_parts = sum(r.participations_collected for r in results)
        errors = [e for r in results for e in r.errors]

        logger.info(
            "process_collector.run.complete",
            sources_processed=len(results),
            total_metrics=total_metrics,
            total_participations=total_parts,
            errors_count=len(errors),
            dry_run=args.dry_run,
        )

        if errors:
            for err in errors:
                logger.error("process_collector.run.error", error=err)
            sys.exit(1)


if __name__ == "__main__":
    main()
