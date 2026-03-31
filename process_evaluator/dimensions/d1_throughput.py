"""D1: Throughput — velocity, cycle time, overdue rate, trend."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import structlog

from ..models import DimensionScore

log = structlog.get_logger("process_evaluator.d1_throughput")


def compute_d1(
    process_id: UUID,
    metrics_rows: list[dict[str, Any]],
    process_def: dict[str, Any],
    conn: psycopg.Connection,
) -> DimensionScore:
    """Compute throughput dimension from recent process_metrics rows.

    Sub-scores (weighted):
        velocity_score  (0.30) — velocity_vs_plan normalized
        cycle_time_score(0.30) — sla_target / avg_cycle_time
        overdue_score   (0.25) — 1 - overdue_rate
        throughput_trend(0.15) — last 4w avg vs prev 4w avg
    """
    if not metrics_rows:
        return DimensionScore(
            name="throughput",
            score=None,
            confidence=0.0,
            evidence={"reason": "no metrics data"},
        )

    weeks = len(metrics_rows)
    sla_target = process_def.get("sla_target_hours") or process_def.get("sla_target")

    # ── velocity_score ──────────────────────────────────────────────
    velocity_vals = [
        r["velocity_vs_plan"] for r in metrics_rows
        if r.get("velocity_vs_plan") is not None
    ]
    if velocity_vals:
        avg_velocity = sum(velocity_vals) / len(velocity_vals)
        # velocity_vs_plan: 1.0 = on plan, >1 = ahead, <1 = behind
        velocity_score = min(1.0, max(0.0, avg_velocity))
    else:
        velocity_score = 0.5  # neutral

    # ── cycle_time_score ────────────────────────────────────────────
    cycle_times = [
        r["avg_cycle_time_hours"] for r in metrics_rows
        if r.get("avg_cycle_time_hours") is not None and r["avg_cycle_time_hours"] > 0
    ]
    if cycle_times and sla_target and sla_target > 0:
        avg_ct = sum(cycle_times) / len(cycle_times)
        cycle_time_score = min(1.0, max(0.0, sla_target / avg_ct))
    elif cycle_times:
        # No SLA — use relative: lower is better, assume median = 0.5
        avg_ct = sum(cycle_times) / len(cycle_times)
        cycle_time_score = 0.5
    else:
        cycle_time_score = 0.5

    # ── overdue_score ───────────────────────────────────────────────
    overdue_rates = [
        r["overdue_rate"] for r in metrics_rows
        if r.get("overdue_rate") is not None
    ]
    if overdue_rates:
        avg_overdue = sum(overdue_rates) / len(overdue_rates)
        overdue_score = max(0.0, 1.0 - avg_overdue)
    else:
        overdue_score = 0.5

    # ── throughput_trend ────────────────────────────────────────────
    throughput_vals = [
        r.get("throughput_count") or r.get("items_completed") or 0
        for r in metrics_rows
    ]
    if len(throughput_vals) >= 8:
        mid = len(throughput_vals) // 2
        recent_avg = sum(throughput_vals[mid:]) / max(1, len(throughput_vals[mid:]))
        prev_avg = sum(throughput_vals[:mid]) / max(1, mid)
        if prev_avg > 0:
            trend_ratio = recent_avg / prev_avg
            trend_score = min(1.0, max(0.0, trend_ratio / 2.0))  # 1.0 ratio = 0.5
        else:
            trend_score = 0.5 if recent_avg == 0 else 1.0
    elif len(throughput_vals) >= 4:
        mid = len(throughput_vals) // 2
        recent_avg = sum(throughput_vals[mid:]) / max(1, len(throughput_vals[mid:]))
        prev_avg = sum(throughput_vals[:mid]) / max(1, mid)
        if prev_avg > 0:
            trend_ratio = recent_avg / prev_avg
            trend_score = min(1.0, max(0.0, trend_ratio / 2.0))
        else:
            trend_score = 0.5
    else:
        trend_score = 0.5

    # ── Composite ───────────────────────────────────────────────────
    raw = (
        0.30 * velocity_score
        + 0.30 * cycle_time_score
        + 0.25 * overdue_score
        + 0.15 * trend_score
    )
    final_score = round(1.0 + raw * 4.0, 2)
    confidence = min(1.0, weeks / 8.0)

    evidence = {
        "velocity_score": round(velocity_score, 3),
        "cycle_time_score": round(cycle_time_score, 3),
        "overdue_score": round(overdue_score, 3),
        "trend_score": round(trend_score, 3),
        "weeks_analyzed": weeks,
    }
    if sla_target:
        evidence["sla_target_hours"] = sla_target
    if cycle_times:
        evidence["avg_cycle_time_hours"] = round(sum(cycle_times) / len(cycle_times), 1)

    log.debug(
        "d1_computed",
        process_id=str(process_id),
        score=final_score,
        confidence=round(confidence, 2),
    )

    return DimensionScore(
        name="throughput",
        score=final_score,
        confidence=round(confidence, 2),
        evidence=evidence,
        sub_scores={
            "velocity": round(velocity_score, 3),
            "cycle_time": round(cycle_time_score, 3),
            "overdue": round(overdue_score, 3),
            "trend": round(trend_score, 3),
        },
    )
