"""D6: Improvement — 90-day trend analysis across all key metrics."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import structlog

from ..models import DimensionScore

log = structlog.get_logger("process_evaluator.d6_improvement")

# Metrics where higher = better
_POSITIVE_METRICS = {
    "velocity_vs_plan", "throughput_count", "items_completed",
    "conversion_rate", "csat_score", "first_contact_resolution",
    "deal_quality_score",
}

# Metrics where lower = better
_NEGATIVE_METRICS = {
    "error_rate", "rework_rate", "overdue_rate", "avg_cycle_time_hours",
    "cost_per_unit", "change_failure_rate", "escalation_rate",
    "budget_variance",
}


def compute_d6(
    process_id: UUID,
    metrics_rows: list[dict[str, Any]],
    conn: psycopg.Connection,
) -> DimensionScore:
    """Compute improvement dimension by analyzing 90-day trends.

    Counts how many metrics are improving vs declining.
    Higher score = more metrics improving.
    """
    if not metrics_rows or len(metrics_rows) < 4:
        return DimensionScore(
            name="improvement",
            score=None,
            confidence=0.0,
            evidence={"reason": "insufficient data for trend analysis", "weeks": len(metrics_rows)},
        )

    weeks = len(metrics_rows)
    mid = weeks // 2
    older_half = metrics_rows[:mid]
    recent_half = metrics_rows[mid:]

    improving = 0
    declining = 0
    stable = 0
    trends: dict[str, str] = {}

    all_metric_keys = _POSITIVE_METRICS | _NEGATIVE_METRICS

    for metric_key in all_metric_keys:
        old_vals = [r[metric_key] for r in older_half if r.get(metric_key) is not None]
        new_vals = [r[metric_key] for r in recent_half if r.get(metric_key) is not None]

        if not old_vals or not new_vals:
            continue

        old_avg = sum(old_vals) / len(old_vals)
        new_avg = sum(new_vals) / len(new_vals)

        if old_avg == 0 and new_avg == 0:
            stable += 1
            trends[metric_key] = "stable"
            continue

        # Determine direction
        if old_avg == 0:
            change_pct = 1.0 if new_avg > 0 else 0.0
        else:
            change_pct = (new_avg - old_avg) / abs(old_avg)

        # Threshold for significance: 5%
        if abs(change_pct) < 0.05:
            stable += 1
            trends[metric_key] = "stable"
        elif metric_key in _POSITIVE_METRICS:
            if change_pct > 0:
                improving += 1
                trends[metric_key] = "improving"
            else:
                declining += 1
                trends[metric_key] = "declining"
        elif metric_key in _NEGATIVE_METRICS:
            if change_pct < 0:  # lower = better for negative metrics
                improving += 1
                trends[metric_key] = "improving"
            else:
                declining += 1
                trends[metric_key] = "declining"

    total_tracked = improving + declining + stable
    if total_tracked == 0:
        return DimensionScore(
            name="improvement",
            score=3.0,  # neutral
            confidence=0.2,
            evidence={"reason": "no trackable metrics found"},
        )

    # Score: ratio of improving to total
    improvement_ratio = improving / total_tracked
    decline_ratio = declining / total_tracked

    # Raw score: full improving = 1.0, full declining = 0.0
    raw = improvement_ratio - 0.5 * decline_ratio + 0.25 * (stable / total_tracked)
    raw = max(0.0, min(1.0, raw))

    final_score = round(1.0 + raw * 4.0, 2)
    confidence = min(1.0, weeks / 8.0) * min(1.0, total_tracked / 3.0)

    evidence = {
        "improving_count": improving,
        "declining_count": declining,
        "stable_count": stable,
        "total_tracked": total_tracked,
        "improvement_ratio": round(improvement_ratio, 3),
        "trends": trends,
        "weeks_analyzed": weeks,
    }

    log.debug(
        "d6_computed",
        process_id=str(process_id),
        score=final_score,
        improving=improving,
        declining=declining,
    )

    return DimensionScore(
        name="improvement",
        score=final_score,
        confidence=round(confidence, 2),
        evidence=evidence,
        sub_scores={
            "improvement_ratio": round(improvement_ratio, 3),
            "decline_ratio": round(decline_ratio, 3),
            "stability_ratio": round(stable / total_tracked, 3) if total_tracked > 0 else 0.0,
        },
    )
