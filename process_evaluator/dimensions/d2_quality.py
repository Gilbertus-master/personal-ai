"""D2: Quality — error rate, rework, CSAT, change failure rate."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import structlog

from ..models import DimensionScore

log = structlog.get_logger("process_evaluator.d2_quality")

# Weights by process type
_WEIGHTS: dict[str, dict[str, float]] = {
    "engineering": {
        "error_rate": 0.30,
        "rework": 0.30,
        "change_failure": 0.40,
    },
    "sales": {
        "conversion": 0.50,
        "deal_quality": 0.50,
    },
    "customer_service": {
        "csat": 0.40,
        "fcr": 0.30,
        "escalation": 0.30,
    },
}


def compute_d2(
    process_id: UUID,
    metrics_rows: list[dict[str, Any]],
    conn: psycopg.Connection,
) -> DimensionScore:
    """Compute quality dimension from process_metrics.

    Weights vary by process_type (engineering, sales, customer_service, default).
    """
    if not metrics_rows:
        return DimensionScore(
            name="quality",
            score=None,
            confidence=0.0,
            evidence={"reason": "no metrics data"},
        )

    # Detect process_type from first row or default
    process_type = metrics_rows[0].get("process_type", "default")
    weeks = len(metrics_rows)

    sub_scores: dict[str, float] = {}
    weights: dict[str, float] = {}

    if process_type == "engineering":
        sub_scores, weights = _score_engineering(metrics_rows)
    elif process_type == "sales":
        sub_scores, weights = _score_sales(metrics_rows)
    elif process_type == "customer_service":
        sub_scores, weights = _score_customer_service(metrics_rows)
    else:
        sub_scores, weights = _score_default(metrics_rows)

    if not sub_scores:
        return DimensionScore(
            name="quality",
            score=None,
            confidence=0.1,
            evidence={"reason": "insufficient quality metrics", "process_type": process_type},
        )

    # Weighted average
    total_weight = sum(weights.get(k, 0) for k in sub_scores)
    if total_weight == 0:
        raw = 0.5
    else:
        raw = sum(sub_scores[k] * weights.get(k, 0) for k in sub_scores) / total_weight

    final_score = round(1.0 + raw * 4.0, 2)
    confidence = min(1.0, weeks / 8.0)

    evidence = {
        "process_type": process_type,
        "weeks_analyzed": weeks,
        **{f"sub_{k}": round(v, 3) for k, v in sub_scores.items()},
    }

    log.debug("d2_computed", process_id=str(process_id), score=final_score)

    return DimensionScore(
        name="quality",
        score=final_score,
        confidence=round(confidence, 2),
        evidence=evidence,
        sub_scores={k: round(v, 3) for k, v in sub_scores.items()},
    )


def _score_engineering(rows: list[dict]) -> tuple[dict[str, float], dict[str, float]]:
    weights = _WEIGHTS["engineering"]
    sub: dict[str, float] = {}

    error_rates = [r["error_rate"] for r in rows if r.get("error_rate") is not None]
    if error_rates:
        sub["error_rate"] = max(0.0, 1.0 - sum(error_rates) / len(error_rates))

    rework_rates = [r["rework_rate"] for r in rows if r.get("rework_rate") is not None]
    if rework_rates:
        sub["rework"] = max(0.0, 1.0 - sum(rework_rates) / len(rework_rates))

    cfr = [r["change_failure_rate"] for r in rows if r.get("change_failure_rate") is not None]
    if cfr:
        sub["change_failure"] = max(0.0, 1.0 - sum(cfr) / len(cfr))

    return sub, weights


def _score_sales(rows: list[dict]) -> tuple[dict[str, float], dict[str, float]]:
    weights = _WEIGHTS["sales"]
    sub: dict[str, float] = {}

    conv = [r["conversion_rate"] for r in rows if r.get("conversion_rate") is not None]
    if conv:
        sub["conversion"] = min(1.0, sum(conv) / len(conv))

    dq = [r["deal_quality_score"] for r in rows if r.get("deal_quality_score") is not None]
    if dq:
        sub["deal_quality"] = min(1.0, sum(dq) / len(dq) / 5.0)  # normalize from 5-scale

    return sub, weights


def _score_customer_service(rows: list[dict]) -> tuple[dict[str, float], dict[str, float]]:
    weights = _WEIGHTS["customer_service"]
    sub: dict[str, float] = {}

    csat = [r["csat_score"] for r in rows if r.get("csat_score") is not None]
    if csat:
        sub["csat"] = min(1.0, sum(csat) / len(csat) / 5.0)

    fcr = [r["first_contact_resolution"] for r in rows if r.get("first_contact_resolution") is not None]
    if fcr:
        sub["fcr"] = min(1.0, sum(fcr) / len(fcr))

    esc = [r["escalation_rate"] for r in rows if r.get("escalation_rate") is not None]
    if esc:
        sub["escalation"] = max(0.0, 1.0 - sum(esc) / len(esc))

    return sub, weights


def _score_default(rows: list[dict]) -> tuple[dict[str, float], dict[str, float]]:
    """Fallback: use whatever quality metrics are available."""
    sub: dict[str, float] = {}
    weights: dict[str, float] = {}

    error_rates = [r["error_rate"] for r in rows if r.get("error_rate") is not None]
    if error_rates:
        sub["error_rate"] = max(0.0, 1.0 - sum(error_rates) / len(error_rates))
        weights["error_rate"] = 0.40

    rework_rates = [r["rework_rate"] for r in rows if r.get("rework_rate") is not None]
    if rework_rates:
        sub["rework"] = max(0.0, 1.0 - sum(rework_rates) / len(rework_rates))
        weights["rework"] = 0.30

    csat = [r["csat_score"] for r in rows if r.get("csat_score") is not None]
    if csat:
        sub["csat"] = min(1.0, sum(csat) / len(csat) / 5.0)
        weights["csat"] = 0.30

    # If nothing found, use neutral
    if not sub:
        sub["neutral"] = 0.5
        weights["neutral"] = 1.0

    return sub, weights
