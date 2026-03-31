"""CLI entrypoint for the Attribution Engine.

Usage:
    python -m attribution_engine.run --all-processes
    python -m attribution_engine.run --process <UUID>
    python -m attribution_engine.run --ceo-report --week 2026-03-24
    python -m attribution_engine.run --dashboard
    python -m attribution_engine.run --human-risk
    python -m attribution_engine.run --waste-report
    python -m attribution_engine.run --migrate
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import UUID

import structlog

log = structlog.get_logger("attribution_engine.run")


def _get_latest_monday() -> date:
    """Return the most recent Monday (start of current week)."""
    today = date.today()
    return today - timedelta(days=today.weekday())


def _run_migration() -> None:
    """Execute the SQL migration."""
    from app.db.postgres import get_pg_connection

    migration_path = Path(__file__).parent / "migrations" / "001_attribution_tables.sql"
    sql = migration_path.read_text()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    log.info("migration_applied", file=str(migration_path))
    print("Migration applied successfully.")


def _upsert_attribution(result, conn) -> None:
    """UPSERT an AttributionResult into the database."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO attribution_results (
                process_id, week_start, direction, severity,
                attribution_process, attribution_people, attribution_interaction,
                attribution_external, attribution_unknown,
                confidence, data_points_count, min_weeks_data,
                process_signals, people_signals, interaction_signals,
                team_id, team_health_contribution,
                top_people_positive, top_people_negative,
                primary_recommendation, recommendation_type,
                narrative, ai_confidence
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s
            )
            ON CONFLICT (process_id, week_start) DO UPDATE SET
                direction = EXCLUDED.direction,
                severity = EXCLUDED.severity,
                attribution_process = EXCLUDED.attribution_process,
                attribution_people = EXCLUDED.attribution_people,
                attribution_interaction = EXCLUDED.attribution_interaction,
                attribution_external = EXCLUDED.attribution_external,
                attribution_unknown = EXCLUDED.attribution_unknown,
                confidence = EXCLUDED.confidence,
                data_points_count = EXCLUDED.data_points_count,
                min_weeks_data = EXCLUDED.min_weeks_data,
                process_signals = EXCLUDED.process_signals,
                people_signals = EXCLUDED.people_signals,
                interaction_signals = EXCLUDED.interaction_signals,
                team_id = EXCLUDED.team_id,
                team_health_contribution = EXCLUDED.team_health_contribution,
                top_people_positive = EXCLUDED.top_people_positive,
                top_people_negative = EXCLUDED.top_people_negative,
                primary_recommendation = EXCLUDED.primary_recommendation,
                recommendation_type = EXCLUDED.recommendation_type,
                narrative = EXCLUDED.narrative,
                ai_confidence = EXCLUDED.ai_confidence,
                computed_at = now()
            """,
            (
                str(result.process_id), result.week_start,
                result.direction, result.severity,
                result.attribution_process, result.attribution_people,
                result.attribution_interaction, result.attribution_external,
                result.attribution_unknown,
                result.confidence, result.data_points_count, result.min_weeks_data,
                json.dumps(result.process_signals, default=str),
                json.dumps(result.people_signals, default=str),
                json.dumps(result.interaction_signals, default=str),
                result.team_id, result.team_health_contribution,
                json.dumps(result.top_people_positive, default=str),
                json.dumps(result.top_people_negative, default=str),
                result.primary_recommendation, result.recommendation_type,
                result.narrative, result.ai_confidence,
            ),
        )
    conn.commit()


def _process_single(process_id: UUID, week_start: date) -> None:
    """Run attribution for a single process."""
    from app.db.postgres import get_pg_connection

    from .anomaly_detector import detect_anomalies
    from .attribution_scorer import calculate_attribution
    from .correlator import correlate_people_process
    from .synthesis import generate_attribution_narrative

    with get_pg_connection() as conn:
        # Step 1: Detect anomalies
        anomalies = detect_anomalies(process_id, None, conn)

        # Step 2: Correlate signals
        signals = correlate_people_process(process_id, week_start, conn)

        # Step 3: Calculate attribution
        result = calculate_attribution(
            process_id, week_start, anomalies,
            signals["people_signals"], signals["process_signals"], conn,
        )

        # Step 4: Generate AI narrative (only for non-neutral)
        if result.direction != "neutral" and result.confidence > 0.2:
            narrative_data = generate_attribution_narrative(result, conn)
            result.narrative = narrative_data.get("narrative")
            result.primary_recommendation = narrative_data.get("primary_recommendation")
            result.recommendation_type = narrative_data.get("recommendation_type")
            result.ai_confidence = result.confidence

        # Step 5: Persist
        _upsert_attribution(result, conn)

        print(f"Process {process_id}: direction={result.direction}, "
              f"severity={result.severity}, confidence={result.confidence:.2f}")
        if result.narrative:
            print(f"  Narrative: {result.narrative}")
        if result.primary_recommendation:
            print(f"  Recommendation: {result.primary_recommendation}")


def _process_all(week_start: date) -> None:
    """Run attribution for all processes."""
    from app.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT process_id FROM processes WHERE status = 'active'")
            rows = cur.fetchall()

    if not rows:
        print("No active processes found.")
        return

    print(f"Processing {len(rows)} active processes for week {week_start}...")

    for row in rows:
        try:
            _process_single(UUID(str(row[0])), week_start)
        except Exception as exc:
            log.error("process_attribution_failed", process_id=str(row[0]), error=str(exc))
            print(f"  ERROR processing {row[0]}: {exc}")


def _generate_ceo_report(week_start: date) -> None:
    """Generate org health snapshot and CEO report."""
    from app.db.postgres import get_pg_connection

    from .synthesis import generate_ceo_weekly_report

    # Import snapshot builder from ceo_dashboard
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from ceo_dashboard.snapshot_builder import compute_org_health_snapshot

    with get_pg_connection() as conn:
        snapshot = compute_org_health_snapshot(week_start, conn)
        report = generate_ceo_weekly_report(snapshot, conn)

    print("\n=== CEO WEEKLY REPORT ===")
    print(f"Week: {week_start}")
    print(f"Org Health: {snapshot.get('org_health_score', '?')}/100 "
          f"({snapshot.get('org_health_label', '?')})")
    print(f"\nHeadline: {report.get('headline', '-')}")
    print(f"\nFinancial: {report.get('financial_insight', '-')}")
    print(f"\nPeople Risk: {report.get('people_risk_insight', '-')}")
    print(f"\nProcesses: {report.get('process_insight', '-')}")
    print("\nTop 3 Actions:")
    for i, action in enumerate(report.get("top_3_actions", []), 1):
        print(f"  {i}. [{action.get('urgency', '?')}] {action.get('action', '-')}")
    print("\nPositive Highlights:")
    for h in report.get("positive_highlights", []):
        print(f"  + {h}")


def _print_dashboard() -> None:
    """Print processes needing attention."""
    from app.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ar.process_id, p.process_name, ar.direction, ar.severity,
                       ar.confidence, ar.narrative, ar.primary_recommendation,
                       pm.health_score
                FROM attribution_results ar
                JOIN processes p ON p.process_id = ar.process_id
                LEFT JOIN process_metrics pm ON pm.process_id = ar.process_id
                    AND pm.week_start = ar.week_start
                WHERE ar.week_start = (SELECT MAX(week_start) FROM attribution_results)
                  AND ar.direction = 'problem'
                ORDER BY
                    CASE ar.severity
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        ELSE 4
                    END,
                    pm.health_score ASC NULLS LAST
                """
            )
            rows = cur.fetchall()

    if not rows:
        print("No processes needing attention.")
        return

    print("\n=== PROCESSES NEEDING ATTENTION ===\n")
    for row in rows:
        (pid, name, direction, severity, confidence,
         narrative, recommendation, health) = row
        health_str = f"{health:.0f}" if health is not None else "?"
        print(f"[{severity.upper()}] {name} (health={health_str}, confidence={confidence:.0%})")
        if narrative:
            print(f"  {narrative}")
        if recommendation:
            print(f"  -> {recommendation}")
        print()


def _print_human_risk() -> None:
    """Print flight risk x process impact report."""
    from app.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.full_name, ecs.flight_risk_score, ecs.overall_score,
                       COUNT(DISTINCT pp.process_id) as process_count,
                       ARRAY_AGG(DISTINCT pr.process_name) as processes
                FROM employee_competency_scores ecs
                JOIN persons p ON p.person_id = ecs.person_id
                JOIN process_participations pp ON pp.person_id = ecs.person_id
                JOIN processes pr ON pr.process_id = pp.process_id
                WHERE ecs.flight_risk_score > 0.5
                  AND ecs.evaluated_at = (
                      SELECT MAX(evaluated_at) FROM employee_competency_scores
                      WHERE person_id = ecs.person_id
                  )
                GROUP BY p.full_name, ecs.flight_risk_score, ecs.overall_score
                ORDER BY ecs.flight_risk_score DESC, process_count DESC
                """
            )
            rows = cur.fetchall()

    if not rows:
        print("No high flight-risk employees found.")
        return

    print("\n=== HUMAN RISK MAP ===\n")
    for row in rows:
        name, risk, delivery, proc_count, processes = row
        procs = ", ".join(processes[:3]) if processes else "-"
        print(f"  {name}: flight_risk={risk:.0%}, delivery={delivery:.1f}/5, "
              f"processes={proc_count} ({procs})")


def _print_waste_report() -> None:
    """Print financial waste report."""
    from app.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.process_name, p.department,
                       pm.cost_per_unit_pln,
                       pm.throughput,
                       pm.overdue_rate,
                       pm.rework_rate,
                       (pm.cost_per_unit_pln * pm.throughput * (pm.overdue_rate + pm.rework_rate))
                           AS estimated_waste_pln_week
                FROM process_metrics pm
                JOIN processes p ON p.process_id = pm.process_id
                WHERE pm.week_start = (SELECT MAX(week_start) FROM process_metrics)
                  AND pm.cost_per_unit_pln IS NOT NULL
                  AND pm.cost_per_unit_pln > 0
                ORDER BY estimated_waste_pln_week DESC NULLS LAST
                LIMIT 20
                """
            )
            rows = cur.fetchall()

    if not rows:
        print("No financial waste data available.")
        return

    print("\n=== FINANCIAL WASTE REPORT ===\n")
    total_waste = 0.0
    for row in rows:
        name, dept, cost_per_unit, throughput, overdue, rework, waste = row
        waste_val = float(waste) if waste else 0.0
        total_waste += waste_val
        print(f"  {name} ({dept}): waste={waste_val:,.0f} PLN/week "
              f"(unit_cost={cost_per_unit:.0f}, throughput={throughput:.0f}, "
              f"overdue={overdue:.0%}, rework={rework:.0%})")
    print(f"\n  TOTAL ESTIMATED WASTE: {total_waste:,.0f} PLN/week")


def main() -> None:
    parser = argparse.ArgumentParser(description="Attribution Engine CLI")
    parser.add_argument("--all-processes", action="store_true",
                        help="Compute attribution for all active processes")
    parser.add_argument("--process", type=str, help="Single process UUID")
    parser.add_argument("--ceo-report", action="store_true", help="Generate CEO weekly report")
    parser.add_argument("--week", type=str, help="Week start date (YYYY-MM-DD), default: latest Monday")
    parser.add_argument("--dashboard", action="store_true", help="Print processes needing attention")
    parser.add_argument("--human-risk", action="store_true", help="Print flight risk x process impact")
    parser.add_argument("--waste-report", action="store_true", help="Print financial waste report")
    parser.add_argument("--migrate", action="store_true", help="Run SQL migration")

    args = parser.parse_args()

    week_start = date.fromisoformat(args.week) if args.week else _get_latest_monday()

    if args.migrate:
        _run_migration()
    elif args.all_processes:
        _process_all(week_start)
    elif args.process:
        _process_single(UUID(args.process), week_start)
    elif args.ceo_report:
        _generate_ceo_report(week_start)
    elif args.dashboard:
        _print_dashboard()
    elif args.human_risk:
        _print_human_risk()
    elif args.waste_report:
        _print_waste_report()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
