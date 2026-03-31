"""D7: Scalability — bottleneck analysis, capacity headroom, breaking point."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from ..models import DimensionScore

log = structlog.get_logger("process_evaluator.d7_scalability")


def compute_d7(
    process_id: UUID,
    metrics_rows: list[dict[str, Any]],
    conn: psycopg.Connection,
) -> DimensionScore:
    """Compute scalability dimension.

    Finds the bottleneck stage and estimates capacity headroom.
    Score mapping:
        >=3.0x headroom -> 5.0
        >=2.0x          -> 4.0
        >=1.5x          -> 3.0
        >=1.2x          -> 2.0
        <1.2x           -> 1.0
    """
    # ── Find bottleneck from stage durations ────────────────────────
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT
                   state_group,
                   AVG(duration_in_prev_state_h) AS avg_duration_h,
                   COUNT(*) AS items
               FROM process_events
               WHERE process_id = %s
                 AND created_at >= CURRENT_DATE - INTERVAL '90 days'
                 AND duration_in_prev_state_h IS NOT NULL
               GROUP BY state_group
               HAVING COUNT(*) >= 3
               ORDER BY avg_duration_h DESC""",
            (str(process_id),),
        )
        stage_rows = cur.fetchall()

    # Also check throughput capacity from metrics
    throughput_vals = [
        r.get("throughput_count") or r.get("items_completed") or 0
        for r in metrics_rows
        if (r.get("throughput_count") or r.get("items_completed") or 0) > 0
    ]
    capacity_vals = [
        r.get("capacity_max") or r.get("max_throughput")
        for r in metrics_rows
        if r.get("capacity_max") or r.get("max_throughput")
    ]

    sub_scores: dict[str, float] = {}
    extra_evidence: dict[str, Any] = {}
    capacity_headroom_pct: float | None = None
    breaking_point_x: float | None = None

    if stage_rows:
        bottleneck = stage_rows[0]
        total_duration = sum(r["avg_duration_h"] for r in stage_rows)

        if total_duration > 0:
            bottleneck_ratio = bottleneck["avg_duration_h"] / total_duration
            # headroom = inverse of concentration in bottleneck
            # If bottleneck is 50% of time, headroom ~2x
            breaking_point_x = round(1.0 / max(bottleneck_ratio, 0.01), 2)
            capacity_headroom_pct = round(max(0, (breaking_point_x - 1.0)) * 100, 1)

            extra_evidence["bottleneck_stage"] = bottleneck["state_group"]
            extra_evidence["bottleneck_avg_h"] = round(bottleneck["avg_duration_h"], 1)
            extra_evidence["bottleneck_ratio"] = round(bottleneck_ratio, 3)
            extra_evidence["stages_analyzed"] = len(stage_rows)

            sub_scores["bottleneck"] = 1.0 - bottleneck_ratio  # lower concentration = better
        else:
            sub_scores["bottleneck"] = 0.5

    elif throughput_vals and capacity_vals:
        avg_throughput = sum(throughput_vals) / len(throughput_vals)
        avg_capacity = sum(capacity_vals) / len(capacity_vals)
        if avg_capacity > 0:
            utilization = avg_throughput / avg_capacity
            breaking_point_x = round(1.0 / max(utilization, 0.01), 2)
            capacity_headroom_pct = round(max(0, (1.0 - utilization)) * 100, 1)
            sub_scores["bottleneck"] = max(0.0, 1.0 - utilization)
            extra_evidence["utilization"] = round(utilization, 3)
        else:
            sub_scores["bottleneck"] = 0.5
    else:
        sub_scores["bottleneck"] = 0.5

    # ── Score from breaking point ───────────────────────────────────
    if breaking_point_x is not None:
        if breaking_point_x >= 3.0:
            final_score = 5.0
        elif breaking_point_x >= 2.0:
            final_score = 4.0
        elif breaking_point_x >= 1.5:
            final_score = 3.0
        elif breaking_point_x >= 1.2:
            final_score = 2.0
        else:
            final_score = 1.0
    else:
        # No data — assume neutral
        final_score = 3.0

    # Confidence
    if stage_rows and len(stage_rows) >= 3:
        confidence = 0.8
    elif stage_rows or (throughput_vals and capacity_vals):
        confidence = 0.5
    else:
        confidence = 0.2

    evidence = {
        "breaking_point_x": breaking_point_x,
        "capacity_headroom_pct": capacity_headroom_pct,
        **{f"sub_{k}": round(v, 3) for k, v in sub_scores.items()},
        **extra_evidence,
    }

    log.debug(
        "d7_computed",
        process_id=str(process_id),
        score=final_score,
        breaking_point=breaking_point_x,
    )

    return DimensionScore(
        name="scalability",
        score=final_score,
        confidence=round(confidence, 2),
        evidence=evidence,
        sub_scores=sub_scores,
    )
