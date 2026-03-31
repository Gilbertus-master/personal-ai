"""CLI entry point for employee_evaluator.

Usage:
    python -m employee_evaluator.run --person UUID --cycle UUID
    python -m employee_evaluator.run --person UUID --cycle UUID --no-ai
    python -m employee_evaluator.run --batch --cycle UUID
    python -m employee_evaluator.run create-cycle --name "Q1 2026" --type quarterly --start 2026-01-01 --end 2026-03-31
    python -m employee_evaluator.run gdpr-access --person UUID
    python -m employee_evaluator.run top --cycle UUID --limit 10
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from uuid import UUID

import structlog

log = structlog.get_logger("employee_evaluator.cli")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Employee Evaluator — multi-dimensional evaluation with GDPR compliance"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ── evaluate (default) ───────────────────────────────────────────
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate employee(s)")
    eval_parser.add_argument("--person", type=str, help="Person UUID")
    eval_parser.add_argument("--cycle", type=str, required=True, help="Cycle UUID")
    eval_parser.add_argument("--batch", action="store_true", help="Evaluate all employees in cycle")
    eval_parser.add_argument("--no-ai", action="store_true", help="Skip AI report generation")
    eval_parser.add_argument(
        "--report-type", type=str, default="manager_only",
        choices=["manager_only", "self_review", "peer_feedback", "full_360"],
    )

    # ── create-cycle ─────────────────────────────────────────────────
    cycle_parser = subparsers.add_parser("create-cycle", help="Create evaluation cycle")
    cycle_parser.add_argument("--name", type=str, required=True, help="Cycle name")
    cycle_parser.add_argument(
        "--type", type=str, default="quarterly",
        choices=["monthly", "quarterly", "semi_annual", "annual", "ad_hoc"],
    )
    cycle_parser.add_argument("--mode", type=str, default="development",
                              choices=["development", "performance"])
    cycle_parser.add_argument("--start", type=str, required=True, help="Period start (YYYY-MM-DD)")
    cycle_parser.add_argument("--end", type=str, required=True, help="Period end (YYYY-MM-DD)")

    # ── gdpr-access ──────────────────────────────────────────────────
    gdpr_parser = subparsers.add_parser("gdpr-access", help="GDPR access request")
    gdpr_parser.add_argument("--person", type=str, required=True, help="Person UUID")

    # ── gdpr-anonymize ───────────────────────────────────────────────
    anon_parser = subparsers.add_parser("gdpr-anonymize", help="GDPR anonymize data")
    anon_parser.add_argument("--person", type=str, required=True, help="Person UUID")

    # ── top ───────────────────────────────────────────────────────────
    top_parser = subparsers.add_parser("top", help="Show top performers in cycle")
    top_parser.add_argument("--cycle", type=str, required=True, help="Cycle UUID")
    top_parser.add_argument("--limit", type=int, default=10, help="Number of results")

    # ── retention-cleanup ────────────────────────────────────────────
    subparsers.add_parser("retention-cleanup", help="Delete expired reports")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to handler
    if args.command == "evaluate":
        _handle_evaluate(args)
    elif args.command == "create-cycle":
        _handle_create_cycle(args)
    elif args.command == "gdpr-access":
        _handle_gdpr_access(args)
    elif args.command == "gdpr-anonymize":
        _handle_gdpr_anonymize(args)
    elif args.command == "top":
        _handle_top(args)
    elif args.command == "retention-cleanup":
        _handle_retention_cleanup()
    else:
        parser.print_help()
        sys.exit(1)


def _handle_evaluate(args: argparse.Namespace) -> None:
    from app.db.postgres import get_pg_connection

    generate_ai = not args.no_ai
    report_types = [args.report_type]

    with get_pg_connection() as conn:
        if args.batch:
            from .batch_runner import run_batch

            result = run_batch(
                cycle_id=UUID(args.cycle),
                conn=conn,
                generate_ai=generate_ai,
                report_types=report_types,
            )
            _print_json(result)
        else:
            if not args.person:
                log.error("--person is required when not using --batch")
                sys.exit(1)

            from .evaluator import evaluate_employee

            result = evaluate_employee(
                person_id=UUID(args.person),
                cycle_id=UUID(args.cycle),
                conn=conn,
                generate_ai=generate_ai,
                report_types=report_types,
            )
            conn.commit()

            output = {
                "person_id": str(result.person_id),
                "display_name": result.display_name,
                "overall_score": result.overall_score,
                "overall_label": result.overall_label,
                "potential_score": result.potential_score,
                "flight_risk_score": result.flight_risk_score,
                "data_completeness": result.data_completeness,
                "nine_box": {
                    "performance": result.nine_box.performance_level,
                    "potential": result.nine_box.potential_level,
                    "label": result.nine_box.label,
                } if result.nine_box else None,
                "competencies": {
                    s.name: {
                        "score": s.score,
                        "confidence": s.confidence,
                    }
                    for s in result.competency_scores
                },
                "requires_human_review": result.requires_human_review,
                "errors": result.errors,
            }
            _print_json(output)


def _handle_create_cycle(args: argparse.Namespace) -> None:
    from app.db.postgres import get_pg_connection
    from psycopg.rows import dict_row

    period_start = date.fromisoformat(args.start)
    period_end = date.fromisoformat(args.end)

    with get_pg_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """INSERT INTO evaluation_cycles
                   (cycle_name, cycle_type, evaluation_mode, period_start, period_end, status)
                   VALUES (%s, %s, %s, %s, %s, 'draft')
                   RETURNING cycle_id, cycle_name, cycle_type, period_start, period_end, status""",
                (args.name, args.type, args.mode, period_start, period_end),
            )
            row = cur.fetchone()
        conn.commit()

    log.info("cycle_created", cycle_id=str(row["cycle_id"]), name=args.name)
    _print_json({
        "cycle_id": str(row["cycle_id"]),
        "cycle_name": row["cycle_name"],
        "cycle_type": row["cycle_type"],
        "period_start": row["period_start"].isoformat(),
        "period_end": row["period_end"].isoformat(),
        "status": row["status"],
    })


def _handle_gdpr_access(args: argparse.Namespace) -> None:
    from app.db.postgres import get_pg_connection
    from .compliance.gdpr_handler import handle_access_request

    person_id = UUID(args.person)
    with get_pg_connection() as conn:
        result = handle_access_request(person_id, conn)
        conn.commit()

    _print_json(result)


def _handle_gdpr_anonymize(args: argparse.Namespace) -> None:
    from app.db.postgres import get_pg_connection
    from .compliance.gdpr_handler import anonymize_employee_data

    person_id = UUID(args.person)
    with get_pg_connection() as conn:
        result = anonymize_employee_data(person_id, conn)
        conn.commit()

    _print_json(result)


def _handle_top(args: argparse.Namespace) -> None:
    from app.db.postgres import get_pg_connection
    from psycopg.rows import dict_row

    cycle_id = UUID(args.cycle)
    limit = args.limit

    with get_pg_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT ecs.person_id, p.display_name,
                          ecs.overall_score, ecs.overall_label,
                          ecs.potential_score, ecs.flight_risk_score,
                          ecs.data_completeness,
                          er.nine_box_label
                   FROM employee_competency_scores ecs
                   JOIN persons p ON p.person_id = ecs.person_id
                   LEFT JOIN employee_reports er
                     ON er.person_id = ecs.person_id
                     AND er.cycle_id = ecs.cycle_id
                     AND er.report_type = 'manager_only'
                   WHERE ecs.cycle_id = %s
                     AND ecs.overall_score IS NOT NULL
                   ORDER BY ecs.overall_score DESC
                   LIMIT %s""",
                (str(cycle_id), limit),
            )
            rows = cur.fetchall()

    output = []
    for i, row in enumerate(rows, 1):
        output.append({
            "rank": i,
            "person_id": str(row["person_id"]),
            "display_name": row["display_name"],
            "overall_score": row["overall_score"],
            "overall_label": row["overall_label"],
            "potential_score": row["potential_score"],
            "flight_risk": row["flight_risk_score"],
            "nine_box": row["nine_box_label"],
            "data_completeness": row["data_completeness"],
        })

    _print_json({"cycle_id": str(cycle_id), "top_performers": output})


def _handle_retention_cleanup() -> None:
    from app.db.postgres import get_pg_connection
    from .compliance.data_retention import cleanup_expired_data

    with get_pg_connection() as conn:
        deleted = cleanup_expired_data(conn)
        conn.commit()

    _print_json({"reports_deleted": deleted})


def _print_json(data: dict) -> None:
    """Print data as formatted JSON to stdout."""
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
