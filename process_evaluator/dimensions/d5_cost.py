"""D5: Cost — cost per unit, budget variance, cost trend."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import structlog

from ..models import DimensionScore

log = structlog.get_logger("process_evaluator.d5_cost")


def compute_d5(
    process_id: UUID,
    metrics_rows: list[dict[str, Any]],
    process_def: dict[str, Any],
    conn: psycopg.Connection,
) -> DimensionScore:
    """Compute cost dimension.

    Sub-scores:
        cost_efficiency (0.40) — actual vs benchmark cost_per_unit
        budget_variance (0.35) — how close to budget
        cost_trend      (0.25) — improving or worsening cost over time
    """
    if not metrics_rows:
        return DimensionScore(
            name="cost",
            score=None,
            confidence=0.0,
            evidence={"reason": "no metrics data"},
        )

    weeks = len(metrics_rows)
    benchmark_cost = process_def.get("cost_per_unit_pln") or process_def.get("budget_per_unit")

    sub_scores: dict[str, float] = {}
    extra_evidence: dict[str, Any] = {}

    # ── Cost efficiency vs benchmark ────────────────────────────────
    cost_vals = [
        r["cost_per_unit"] for r in metrics_rows
        if r.get("cost_per_unit") is not None and r["cost_per_unit"] > 0
    ]
    if cost_vals:
        avg_cost = sum(cost_vals) / len(cost_vals)
        extra_evidence["avg_cost_per_unit"] = round(avg_cost, 2)

        if benchmark_cost and benchmark_cost > 0:
            ratio = avg_cost / benchmark_cost
            extra_evidence["cost_vs_benchmark"] = round(ratio, 3)
            # ratio 1.0 = on target (0.7 score), <0.8 = excellent (1.0), >1.5 = bad (0.0)
            cost_efficiency = max(0.0, min(1.0, 1.0 - (ratio - 0.8) / 0.7))
            sub_scores["cost_efficiency"] = cost_efficiency
        else:
            sub_scores["cost_efficiency"] = 0.5
    else:
        sub_scores["cost_efficiency"] = 0.5

    # ── Budget variance ─────────────────────────────────────────────
    budget_vars = [
        r["budget_variance"] for r in metrics_rows
        if r.get("budget_variance") is not None
    ]
    if budget_vars:
        avg_var = sum(budget_vars) / len(budget_vars)
        # budget_variance: 0 = on budget, negative = under, positive = over
        # Score: on budget = 1.0, 20% over = 0.0
        budget_score = max(0.0, min(1.0, 1.0 - abs(avg_var) / 0.2))
        sub_scores["budget_variance"] = budget_score
        extra_evidence["avg_budget_variance"] = round(avg_var, 3)
    else:
        sub_scores["budget_variance"] = 0.5

    # ── Cost trend ──────────────────────────────────────────────────
    if cost_vals and len(cost_vals) >= 4:
        mid = len(cost_vals) // 2
        recent_avg = sum(cost_vals[mid:]) / len(cost_vals[mid:])
        prev_avg = sum(cost_vals[:mid]) / mid
        if prev_avg > 0:
            trend_ratio = recent_avg / prev_avg
            # <1.0 = costs decreasing (good), >1.0 = costs increasing (bad)
            trend_score = max(0.0, min(1.0, 2.0 - trend_ratio))
            sub_scores["cost_trend"] = trend_score
            extra_evidence["cost_trend_ratio"] = round(trend_ratio, 3)
        else:
            sub_scores["cost_trend"] = 0.5
    else:
        sub_scores["cost_trend"] = 0.5

    # ── Composite ───────────────────────────────────────────────────
    raw = (
        0.40 * sub_scores.get("cost_efficiency", 0.5)
        + 0.35 * sub_scores.get("budget_variance", 0.5)
        + 0.25 * sub_scores.get("cost_trend", 0.5)
    )
    final_score = round(1.0 + raw * 4.0, 2)
    confidence = min(1.0, weeks / 8.0)

    # Reduce confidence if no benchmark
    if not benchmark_cost:
        confidence *= 0.6

    evidence = {
        "weeks_analyzed": weeks,
        "has_benchmark": benchmark_cost is not None,
        **{f"sub_{k}": round(v, 3) for k, v in sub_scores.items()},
        **extra_evidence,
    }

    log.debug("d5_computed", process_id=str(process_id), score=final_score)

    return DimensionScore(
        name="cost",
        score=final_score,
        confidence=round(confidence, 2),
        evidence=evidence,
        sub_scores={k: round(v, 3) for k, v in sub_scores.items()},
    )
