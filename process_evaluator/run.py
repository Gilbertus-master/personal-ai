"""CLI entry point for process_evaluator.

Usage:
    python -m process_evaluator.run --all
    python -m process_evaluator.run --process UUID
    python -m process_evaluator.run --process UUID --no-ai
    python -m process_evaluator.run --human-risk
    python -m process_evaluator.run --matrix
    python -m process_evaluator.run --send-maturity-survey
    python -m process_evaluator.run --record-survey PROCESS_ID S1 S2 S3 S4 S5
    python -m process_evaluator.run --migrate
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from uuid import UUID

import structlog

log = structlog.get_logger("process_evaluator.cli")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process Evaluator — 8-dimension health scoring for business processes"
    )
    parser.add_argument("--all", action="store_true", help="Evaluate all active processes")
    parser.add_argument("--process", type=str, help="Single process UUID to evaluate")
    parser.add_argument("--cycle", type=str, help="Evaluation cycle UUID (optional)")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI narrative generation")
    parser.add_argument("--human-risk", action="store_true", help="Show processes at human risk")
    parser.add_argument("--matrix", action="store_true", help="Show process health matrix")
    parser.add_argument(
        "--send-maturity-survey", action="store_true",
        help="List processes needing PML maturity survey",
    )
    parser.add_argument(
        "--record-survey", nargs=6, metavar=("PROCESS_ID", "S1", "S2", "S3", "S4", "S5"),
        help="Record maturity survey: PROCESS_ID followed by 5 scores (1-5)",
    )
    parser.add_argument("--migrate", action="store_true", help="Run SQL migration")

    args = parser.parse_args()

    # At least one action required
    if not any([
        args.all, args.process, args.human_risk, args.matrix,
        args.send_maturity_survey, args.record_survey, args.migrate,
    ]):
        parser.print_help()
        sys.exit(1)

    if args.migrate:
        _handle_migrate()
        return

    if args.all:
        _handle_batch(args)
    elif args.process:
        _handle_single(args)
    elif args.human_risk:
        _handle_human_risk()
    elif args.matrix:
        _handle_matrix()
    elif args.send_maturity_survey:
        _handle_pending_surveys()
    elif args.record_survey:
        _handle_record_survey(args)


def _handle_migrate() -> None:
    """Run SQL migration."""
    from app.db.postgres import get_pg_connection

    migration_path = os.path.join(
        os.path.dirname(__file__), "migrations", "001_process_evaluator.sql"
    )
    with open(migration_path, "r") as f:
        sql = f.read()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    log.info("migration_applied", file="001_process_evaluator.sql")
    print("Migration 001_process_evaluator.sql applied successfully.")


def _handle_batch(args: argparse.Namespace) -> None:
    from app.db.postgres import get_pg_connection
    from .batch_runner import run_batch

    cycle_id = UUID(args.cycle) if args.cycle else None
    generate_ai = not args.no_ai

    with get_pg_connection() as conn:
        result = run_batch(
            cycle_id=cycle_id,
            conn=conn,
            generate_ai=generate_ai,
        )

    _print_json(result)


def _handle_single(args: argparse.Namespace) -> None:
    from app.db.postgres import get_pg_connection
    from .evaluator import evaluate_process

    process_id = UUID(args.process)
    cycle_id = UUID(args.cycle) if args.cycle else None
    generate_ai = not args.no_ai

    with get_pg_connection() as conn:
        result = evaluate_process(
            process_id=process_id,
            cycle_id=cycle_id,
            conn=conn,
            generate_ai=generate_ai,
        )
        conn.commit()

    output = {
        "process_id": str(result.process_id),
        "process_name": result.process_name,
        "overall_health_score": result.overall_health_score,
        "health_label": result.health_label,
        "failure_risk_score": result.failure_risk_score,
        "process_box": {
            "health": result.process_box.health_level,
            "maturity": result.process_box.maturity_level,
            "label": result.process_box.label,
        } if result.process_box else None,
        "dimensions": {
            s.name: {
                "score": s.score,
                "confidence": s.confidence,
            }
            for s in result.dimension_scores
        },
        "bus_factor": result.bus_factor,
        "flight_risk_weighted": result.flight_risk_weighted,
        "knowledge_concentration": result.knowledge_concentration,
        "critical_person_ids": [str(pid) for pid in result.critical_person_ids],
        "data_completeness": result.data_completeness,
        "requires_human_review": result.requires_human_review,
        "ai_narrative": result.ai_narrative,
        "ai_key_findings": result.ai_key_findings,
        "ai_recommendations": result.ai_recommendations,
        "errors": result.errors,
    }
    _print_json(output)


def _handle_human_risk() -> None:
    from app.db.postgres import get_pg_connection
    from psycopg.rows import dict_row

    with get_pg_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM v_processes_at_human_risk")
            rows = cur.fetchall()

    if not rows:
        print("No processes at human risk found.")
        return

    output = []
    for row in rows:
        output.append({
            "process_id": str(row["process_id"]),
            "process_name": row["process_name"],
            "process_type": row["process_type"],
            "health_score": row["overall_health_score"],
            "health_label": row["health_label"],
            "failure_risk": row["failure_risk_score"],
            "bus_factor": row["bus_factor"],
            "flight_risk_weighted": row["flight_risk_weighted"],
            "knowledge_concentration": row["knowledge_concentration"],
            "critical_persons": row.get("critical_persons_detail"),
        })

    _print_json({"processes_at_human_risk": output, "count": len(output)})


def _handle_matrix() -> None:
    from app.db.postgres import get_pg_connection
    from psycopg.rows import dict_row

    with get_pg_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM v_process_matrix")
            rows = cur.fetchall()

    if not rows:
        print("No process evaluations found. Run --all first.")
        return

    output = []
    for row in rows:
        output.append({
            "process_id": str(row["process_id"]),
            "process_name": row["process_name"],
            "process_type": row["process_type"],
            "health_score": row["overall_health_score"],
            "health_label": row["health_label"],
            "failure_risk": row["failure_risk_score"],
            "box_label": row["process_box_label"],
            "D1_throughput": row["score_throughput"],
            "D2_quality": row["score_quality"],
            "D3_maturity": row["score_maturity"],
            "D4_handoff": row["score_handoff"],
            "D5_cost": row["score_cost"],
            "D6_improvement": row["score_improvement"],
            "D7_scalability": row["score_scalability"],
            "D8_dependency": row["score_dependency"],
            "bus_factor": row["bus_factor"],
            "pml": row["process_maturity_level"],
            "data_completeness": row["data_completeness"],
        })

    _print_json({"process_matrix": output, "count": len(output)})


def _handle_pending_surveys() -> None:
    from app.db.postgres import get_pg_connection
    from .maturity_survey import get_pending_surveys, get_survey_questions

    with get_pg_connection() as conn:
        pending = get_pending_surveys(conn)

    if not pending:
        print("All processes have recent maturity surveys.")
        return

    questions = get_survey_questions()

    _print_json({
        "pending_surveys": pending,
        "count": len(pending),
        "survey_questions": questions,
        "usage": "python -m process_evaluator.run --record-survey PROCESS_ID S1 S2 S3 S4 S5",
    })


def _handle_record_survey(args: argparse.Namespace) -> None:
    from app.db.postgres import get_pg_connection
    from .maturity_survey import record_survey_response

    process_id = UUID(args.record_survey[0])
    scores = [int(s) for s in args.record_survey[1:]]

    with get_pg_connection() as conn:
        result = record_survey_response(process_id, scores, conn)

    _print_json(result)


def _print_json(data: dict) -> None:
    """Print data as formatted JSON to stdout."""
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


if __name__ == "__main__":
    main()
