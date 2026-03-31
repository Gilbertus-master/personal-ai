"""D4: Handoff — transition efficiency between process stages."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from ..models import DimensionScore

log = structlog.get_logger("process_evaluator.d4_handoff")


def compute_d4(
    process_id: UUID,
    metrics_rows: list[dict[str, Any]],
    conn: psycopg.Connection,
) -> DimensionScore:
    """Compute handoff dimension from state transitions.

    Analyzes:
        - Average wait time between stages (from process_events)
        - Blocker rate
        - Handoff error proxy (rework after state change)
    """
    sub_scores: dict[str, float] = {}

    # ── Wait times between stages ───────────────────────────────────
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT
                   state_group,
                   AVG(duration_in_prev_state_h) AS avg_wait_h,
                   COUNT(*) AS transition_count
               FROM process_events
               WHERE process_id = %s
                 AND created_at >= CURRENT_DATE - INTERVAL '90 days'
                 AND duration_in_prev_state_h IS NOT NULL
               GROUP BY state_group
               ORDER BY avg_wait_h DESC""",
            (str(process_id),),
        )
        stage_rows = cur.fetchall()

    total_transitions = 0
    if stage_rows:
        avg_waits = [r["avg_wait_h"] for r in stage_rows if r["avg_wait_h"] is not None]
        total_transitions = sum(r["transition_count"] for r in stage_rows)

        if avg_waits:
            overall_avg_wait = sum(avg_waits) / len(avg_waits)
            # Normalize: <1h = excellent (1.0), >24h = bad (0.0)
            wait_score = max(0.0, min(1.0, 1.0 - (overall_avg_wait / 24.0)))
            sub_scores["wait_time"] = wait_score
        else:
            sub_scores["wait_time"] = 0.5

        # Max wait (bottleneck stage)
        max_wait = max(avg_waits) if avg_waits else 0
        sub_scores["bottleneck_wait_h"] = max_wait
    else:
        sub_scores["wait_time"] = 0.5

    # ── Blocker rate ────────────────────────────────────────────────
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT
                   COUNT(*) FILTER (WHERE event_type = 'blocked') AS blocked_count,
                   COUNT(*) AS total_events
               FROM process_events
               WHERE process_id = %s
                 AND created_at >= CURRENT_DATE - INTERVAL '90 days'""",
            (str(process_id),),
        )
        blocker_row = cur.fetchone()

    if blocker_row and blocker_row["total_events"] > 0:
        blocker_rate = blocker_row["blocked_count"] / blocker_row["total_events"]
        sub_scores["blocker"] = max(0.0, 1.0 - blocker_rate * 5.0)  # 20% blockers = 0.0
    else:
        sub_scores["blocker"] = 0.5

    # ── Handoff error proxy ─────────────────────────────────────────
    # Use rework_rate from metrics as proxy for handoff errors
    rework_vals = [
        r["rework_rate"] for r in metrics_rows
        if r.get("rework_rate") is not None
    ]
    if rework_vals:
        avg_rework = sum(rework_vals) / len(rework_vals)
        sub_scores["handoff_error"] = max(0.0, 1.0 - avg_rework * 2.0)
    else:
        sub_scores["handoff_error"] = 0.5

    # ── Composite ───────────────────────────────────────────────────
    raw = (
        0.45 * sub_scores.get("wait_time", 0.5)
        + 0.30 * sub_scores.get("blocker", 0.5)
        + 0.25 * sub_scores.get("handoff_error", 0.5)
    )
    final_score = round(1.0 + raw * 4.0, 2)

    # Confidence based on data availability
    if total_transitions >= 20:
        confidence = 0.9
    elif total_transitions >= 10:
        confidence = 0.7
    elif total_transitions > 0:
        confidence = 0.4
    else:
        confidence = 0.2

    evidence = {
        "total_transitions": total_transitions,
        "stages_analyzed": len(stage_rows) if stage_rows else 0,
        **{f"sub_{k}": round(v, 3) for k, v in sub_scores.items()
           if k != "bottleneck_wait_h"},
    }
    if "bottleneck_wait_h" in sub_scores:
        evidence["bottleneck_wait_h"] = round(sub_scores["bottleneck_wait_h"], 1)

    log.debug("d4_computed", process_id=str(process_id), score=final_score)

    return DimensionScore(
        name="handoff",
        score=final_score,
        confidence=round(confidence, 2),
        evidence=evidence,
        sub_scores={k: round(v, 3) for k, v in sub_scores.items()},
    )
