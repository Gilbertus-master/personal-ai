"""CLI entry point for relationship_analyzer.

Usage:
    # Analyze a single pair
    python -m relationship_analyzer.run --person-a UUID --person-b UUID

    # Analyze with no AI narrative
    python -m relationship_analyzer.run --person-a UUID --person-b UUID --no-ai

    # Batch: analyze all pairs above threshold
    python -m relationship_analyzer.run --batch --min-tie-strength 0.2

    # Top N relationships (for Sebastian)
    python -m relationship_analyzer.run --top 10

    # Batch with limit
    python -m relationship_analyzer.run --batch --min-tie-strength 0.1 --limit 50
"""

from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger("relationship_analyzer.run")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Relationship Analyzer — deep relationship analysis between persons.",
    )

    # Single pair mode
    parser.add_argument("--person-a", type=str, help="UUID of person A")
    parser.add_argument("--person-b", type=str, help="UUID of person B")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI narrative generation")
    parser.add_argument("--window", type=int, default=365, help="Data window in days (default: 365)")

    # Batch mode
    parser.add_argument("--batch", action="store_true", help="Run batch analysis for all pairs")
    parser.add_argument(
        "--min-tie-strength", type=float, default=0.2,
        help="Minimum tie_strength for batch (default: 0.2)",
    )
    parser.add_argument("--limit", type=int, help="Max pairs in batch mode")

    # Top N mode
    parser.add_argument("--top", type=int, help="Show top N relationships for Sebastian")

    # Run migration
    parser.add_argument("--migrate", action="store_true", help="Run SQL migration")

    return parser.parse_args()


def _run_single(person_a: str, person_b: str, no_ai: bool, window: int) -> None:
    """Analyze a single pair."""
    from .analyzer import analyze_relationship

    with get_pg_connection() as conn:
        result = analyze_relationship(
            UUID(person_a),
            UUID(person_b),
            conn,
            data_window_days=window,
            generate_ai=not no_ai,
        )

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


def _run_batch(min_tie_strength: float, limit: int | None, no_ai: bool) -> None:
    """Run batch analysis."""
    from .batch_runner import run_batch

    with get_pg_connection() as conn:
        stats = run_batch(
            conn,
            min_tie_strength=min_tie_strength,
            generate_ai_for_strong=not no_ai,
            limit=limit,
        )

    print(json.dumps(stats, indent=2, ensure_ascii=False))


def _run_top(top_n: int) -> None:
    """Show top N relationships from v_my_top_relationships view."""
    from psycopg.rows import dict_row

    with get_pg_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM v_my_top_relationships LIMIT %s",
                (top_n,),
            )
            rows = cur.fetchall()

    if not rows:
        print("No relationship analyses found. Run --batch first.")
        return

    for i, row in enumerate(rows, 1):
        print(f"\n{'='*60}")
        print(f"#{i} {row.get('name_b', '?')} ({row.get('job_title', '')} @ {row.get('company', '')})")
        print(f"  Health: {row.get('health_score')}/100 ({row.get('health_label', '?')})")
        print(f"  Lifecycle: {row.get('lifecycle_stage', '?')}")
        print(f"  Trajectory: {row.get('trajectory_status', '?')}")
        print(f"  Tie strength: {row.get('tie_strength_current')}")
        print(f"  Interactions: {row.get('interaction_count_total')}")
        print(f"  Days since contact: {row.get('days_since_last_contact')}")
        print(f"  Initiation ratio: {row.get('initiation_ratio')}")
        print(f"  Open loops: {row.get('open_loops_count')}")
        if row.get("narrative_summary"):
            print(f"  Narrative: {row['narrative_summary'][:200]}...")
        if row.get("recommended_action"):
            print(f"  Action: {row['recommended_action']}")
        if row.get("key_strengths"):
            print(f"  Strengths: {', '.join(row['key_strengths'][:3])}")
        if row.get("key_risks"):
            print(f"  Risks: {', '.join(row['key_risks'][:3])}")


def _run_migration() -> None:
    """Run the SQL migration."""
    import os

    migration_path = os.path.join(
        os.path.dirname(__file__), "migrations", "001_relationship_analyses.sql"
    )

    with open(migration_path) as f:
        sql = f.read()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    print("Migration applied successfully.")


def main() -> None:
    args = _parse_args()

    if args.migrate:
        _run_migration()
        return

    if args.top:
        _run_top(args.top)
        return

    if args.batch:
        _run_batch(args.min_tie_strength, args.limit, args.no_ai)
        return

    if args.person_a and args.person_b:
        _run_single(args.person_a, args.person_b, args.no_ai, args.window)
        return

    print("Usage: python -m relationship_analyzer.run --help", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
