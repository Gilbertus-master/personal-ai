"""First-run initialization script.

Usage:
    python -m person_profile.init_db [--owner-name "Sebastian Jabłoński"]
    python -m person_profile.init_db --full-rebuild

Steps:
1. Execute migrations/001_initial_schema.sql
2. Create 'me' record in persons (is_me = true)
3. Initialize pipeline_state for all sources
4. Optionally trigger a full (non-delta) pipeline rebuild
"""

from __future__ import annotations

import argparse
from pathlib import Path

import structlog

from app.db.postgres import get_pg_connection

from . import config as cfg

log = structlog.get_logger("person_profile.init_db")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations(conn) -> None:
    """Execute all SQL migration files in order."""
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        log.warning("no_migrations_found", dir=str(MIGRATIONS_DIR))
        return

    for mf in migration_files:
        log.info("executing_migration", file=mf.name)
        sql = mf.read_text(encoding="utf-8")
        conn.execute(sql)
    conn.commit()
    log.info("migrations_complete", count=len(migration_files))


def create_owner(conn, owner_name: str) -> None:
    """Create the 'me' record if it doesn't exist."""
    existing = conn.execute(
        "SELECT person_id FROM persons WHERE is_me = true"
    ).fetchone()

    if existing:
        log.info("owner_exists", person_id=str(existing[0]))
        return

    row = conn.execute(
        """INSERT INTO persons (display_name, is_me, tags)
           VALUES (%s, true, %s)
           RETURNING person_id""",
        (owner_name, ["owner"]),
    ).fetchone()
    conn.commit()
    log.info("owner_created", person_id=str(row[0]), name=owner_name)


def init_pipeline_state(conn) -> None:
    """Initialize pipeline_state rows for all known sources."""
    for source in cfg.PIPELINE_SOURCES:
        conn.execute(
            """INSERT INTO pipeline_state (source_name, status)
               VALUES (%s, 'never_run')
               ON CONFLICT (source_name) DO NOTHING""",
            (source,),
        )
    conn.commit()
    log.info("pipeline_state_initialized", sources=len(cfg.PIPELINE_SOURCES))


def init_db(owner_name: str = "Sebastian Jabłoński", full_rebuild: bool = False) -> None:
    """Run the full initialization sequence."""
    with get_pg_connection() as conn:
        # Step 1: Migrations
        run_migrations(conn)

        # Step 2: Owner record
        create_owner(conn, owner_name)

        # Step 3: Pipeline state
        init_pipeline_state(conn)

    log.info("init_db_complete")

    # Step 4: Optional full rebuild
    if full_rebuild:
        log.info("starting_full_rebuild")
        from .delta_pipeline import run_delta_pipeline
        result = run_delta_pipeline(full_rebuild=True)
        log.info("full_rebuild_complete", result=result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize person_profile database")
    parser.add_argument(
        "--owner-name",
        default="Sebastian Jabłoński",
        help="Display name for the owner (is_me=true) record",
    )
    parser.add_argument(
        "--full-rebuild",
        action="store_true",
        help="Run full delta pipeline after schema setup",
    )
    args = parser.parse_args()

    init_db(owner_name=args.owner_name, full_rebuild=args.full_rebuild)


if __name__ == "__main__":
    main()
