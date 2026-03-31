"""Batch evaluation runner: process multiple employees in a cycle."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from .compliance.audit_logger import log_action
from .config import BATCH_COMMIT_EVERY
from .evaluator import evaluate_employee
from .models import EvaluationResult

log = structlog.get_logger("employee_evaluator.batch_runner")


def run_batch(
    cycle_id: UUID,
    conn: psycopg.Connection,
    person_ids: list[UUID] | None = None,
    generate_ai: bool = True,
    report_types: list[str] | None = None,
) -> dict[str, Any]:
    """Run evaluations for multiple employees.

    If person_ids is None, evaluates all persons with employee_signals
    in the cycle period.

    Commits every BATCH_COMMIT_EVERY employees for resilience.

    Args:
        cycle_id: Evaluation cycle UUID.
        conn: Database connection (autocommit should be OFF).
        person_ids: Specific persons to evaluate, or None for all.
        generate_ai: Whether to generate AI narratives.
        report_types: Report types to generate per employee.

    Returns:
        Summary dict with counts and any errors.
    """
    if report_types is None:
        report_types = ["manager_only"]

    # ── Resolve person list ──────────────────────────────────────────
    if person_ids is None:
        person_ids = _get_cycle_persons(cycle_id, conn)

    total = len(person_ids)
    log.info("batch_started", cycle_id=str(cycle_id), total=total, generate_ai=generate_ai)
    log_action("batch_started", None, {"cycle_id": str(cycle_id), "total": total}, "system", conn)

    results: list[EvaluationResult] = []
    errors: list[dict[str, Any]] = []
    processed = 0

    for i, pid in enumerate(person_ids):
        try:
            result = evaluate_employee(
                person_id=pid,
                cycle_id=cycle_id,
                conn=conn,
                generate_ai=generate_ai,
                report_types=report_types,
            )
            results.append(result)
            processed += 1

            if result.errors:
                errors.append({
                    "person_id": str(pid),
                    "errors": result.errors,
                })

        except Exception as e:
            log.error(
                "batch_employee_failed",
                person_id=str(pid),
                error=str(e),
                error_type=type(e).__name__,
            )
            errors.append({
                "person_id": str(pid),
                "errors": [str(e)],
            })

        # Commit every N employees
        if (i + 1) % BATCH_COMMIT_EVERY == 0:
            conn.commit()
            log.info("batch_checkpoint", processed=i + 1, total=total)

    # Final commit
    conn.commit()

    # ── Update cycle status ──────────────────────────────────────────
    _update_cycle_status(cycle_id, "review", conn)
    conn.commit()

    summary = {
        "cycle_id": str(cycle_id),
        "total_persons": total,
        "processed": processed,
        "errors_count": len(errors),
        "errors": errors,
        "avg_overall_score": _avg_score(results),
        "score_distribution": _score_distribution(results),
    }

    log_action("batch_completed", None, summary, "system", conn)
    conn.commit()

    log.info(
        "batch_completed",
        cycle_id=str(cycle_id),
        processed=processed,
        errors=len(errors),
    )
    return summary


def _get_cycle_persons(cycle_id: UUID, conn: psycopg.Connection) -> list[UUID]:
    """Get all person_ids that have signals in the cycle period."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT DISTINCT es.person_id
               FROM employee_signals es
               JOIN evaluation_cycles ec ON ec.cycle_id = %s
               WHERE es.week_start >= ec.period_start
                 AND es.week_start <= ec.period_end
               ORDER BY es.person_id""",
            (str(cycle_id),),
        )
        rows = cur.fetchall()
    return [row["person_id"] for row in rows]


def _update_cycle_status(
    cycle_id: UUID, status: str, conn: psycopg.Connection
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE evaluation_cycles SET status = %s, updated_at = NOW()
               WHERE cycle_id = %s""",
            (status, str(cycle_id)),
        )


def _avg_score(results: list[EvaluationResult]) -> float | None:
    scores = [r.overall_score for r in results if r.overall_score is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _score_distribution(results: list[EvaluationResult]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for r in results:
        label = r.overall_label or "no_score"
        dist[label] = dist.get(label, 0) + 1
    return dist
