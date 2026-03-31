"""Batch evaluation runner: process multiple business processes in a cycle."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from .evaluator import evaluate_process
from .models import ProcessEvaluationResult

log = structlog.get_logger("process_evaluator.batch_runner")

BATCH_COMMIT_EVERY = 10
MIN_WEEKS_DATA = 4


def run_batch(
    cycle_id: UUID | None,
    conn: psycopg.Connection,
    process_ids: list[UUID] | None = None,
    generate_ai: bool = True,
) -> dict[str, Any]:
    """Run evaluations for multiple processes.

    If process_ids is None, evaluates all active processes with sufficient data.
    Skips processes with <4 weeks of metrics data.
    Commits every 10 processes for resilience.

    Args:
        cycle_id: Evaluation cycle UUID (can be None for ad-hoc).
        conn: Database connection (autocommit should be OFF).
        process_ids: Specific processes to evaluate, or None for all.
        generate_ai: Whether to generate AI narratives.

    Returns:
        Summary dict with counts and any errors.
    """
    # ── Resolve process list ────────────────────────────────────────
    if process_ids is None:
        process_ids = _get_eligible_processes(conn)

    total = len(process_ids)
    log.info(
        "batch_started",
        cycle_id=str(cycle_id) if cycle_id else None,
        total=total,
        generate_ai=generate_ai,
    )

    results: list[ProcessEvaluationResult] = []
    errors: list[dict[str, Any]] = []
    skipped = 0
    processed = 0

    for i, pid in enumerate(process_ids):
        # Check minimum data
        week_count = _count_metric_weeks(pid, conn)
        if week_count < MIN_WEEKS_DATA:
            log.debug(
                "process_skipped_insufficient_data",
                process_id=str(pid),
                weeks=week_count,
                min_required=MIN_WEEKS_DATA,
            )
            skipped += 1
            continue

        try:
            result = evaluate_process(
                process_id=pid,
                cycle_id=cycle_id,
                conn=conn,
                generate_ai=generate_ai,
            )
            results.append(result)
            processed += 1

            if result.errors:
                errors.append({
                    "process_id": str(pid),
                    "process_name": result.process_name,
                    "errors": result.errors,
                })

        except Exception as e:
            log.error(
                "batch_process_failed",
                process_id=str(pid),
                error=str(e),
                error_type=type(e).__name__,
            )
            errors.append({
                "process_id": str(pid),
                "errors": [str(e)],
            })

        # Commit every N processes
        if (i + 1) % BATCH_COMMIT_EVERY == 0:
            conn.commit()
            log.info("batch_checkpoint", processed=processed, total=total)

    # Final commit
    conn.commit()

    summary = {
        "cycle_id": str(cycle_id) if cycle_id else None,
        "total_processes": total,
        "processed": processed,
        "skipped_insufficient_data": skipped,
        "errors_count": len(errors),
        "errors": errors,
        "avg_health_score": _avg_health(results),
        "health_distribution": _health_distribution(results),
        "high_risk_count": sum(
            1 for r in results
            if r.failure_risk_score is not None and r.failure_risk_score > 0.6
        ),
    }

    log.info(
        "batch_completed",
        processed=processed,
        skipped=skipped,
        errors=len(errors),
        avg_health=summary["avg_health_score"],
    )

    return summary


def _get_eligible_processes(conn: psycopg.Connection) -> list[UUID]:
    """Get all active processes."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT process_id
               FROM processes
               WHERE status = 'active'
               ORDER BY process_name""",
        )
        rows = cur.fetchall()
    return [row["process_id"] for row in rows]


def _count_metric_weeks(process_id: UUID, conn: psycopg.Connection) -> int:
    """Count distinct metric weeks for a process in the last 90 days."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT COUNT(DISTINCT DATE_TRUNC('week', metric_date))
               FROM process_metrics
               WHERE process_id = %s
                 AND metric_date >= CURRENT_DATE - INTERVAL '90 days'""",
            (str(process_id),),
        )
        row = cur.fetchone()
    return row[0] if row else 0


def _avg_health(results: list[ProcessEvaluationResult]) -> float | None:
    scores = [r.overall_health_score for r in results if r.overall_health_score is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def _health_distribution(results: list[ProcessEvaluationResult]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for r in results:
        label = r.health_label or "no_score"
        dist[label] = dist.get(label, 0) + 1
    return dist
