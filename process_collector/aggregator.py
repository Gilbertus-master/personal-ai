"""Health-score calculation and anomaly detection for process metrics."""

from __future__ import annotations

import math
from typing import Any

import psycopg
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------
# Weight definitions per process_type
# ---------------------------------------------------------------
_WEIGHTS: dict[str, dict[str, float]] = {
    "engineering": {
        "velocity": 0.30,
        "quality": 0.25,
        "flow": 0.20,
        "reliability": 0.15,
        "debt": 0.10,
    },
    "sales": {
        "revenue": 0.35,
        "efficiency": 0.30,
        "pipeline": 0.20,
        "conversion": 0.15,
    },
    "customer_service": {
        "speed": 0.30,
        "quality": 0.25,
        "resolution": 0.25,
        "escalation": 0.20,
    },
    "finance": {
        "budget": 0.40,
        "margin": 0.35,
        "efficiency": 0.25,
    },
    "operations": {
        "throughput": 0.30,
        "quality": 0.25,
        "timeliness": 0.25,
        "cost": 0.20,
    },
}


# ---------------------------------------------------------------
# Helpers: simple stats without numpy
# ---------------------------------------------------------------

def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


# ---------------------------------------------------------------
# Component scorers (return 0-100)
# ---------------------------------------------------------------

def _score_engineering(metrics: dict[str, Any]) -> dict[str, float]:
    """Score engineering metrics into component scores 0-100."""
    scores: dict[str, float] = {}

    # Velocity: velocity_vs_plan close to 1.0 is ideal
    vp = metrics.get("velocity_vs_plan")
    if vp is not None and vp > 0:
        scores["velocity"] = _clamp(vp * 100)
    else:
        scores["velocity"] = 50.0

    # Quality: low bug rate + low rework
    bugs = metrics.get("bugs_introduced", 0) or 0
    throughput = metrics.get("throughput", 1) or 1
    rework = metrics.get("rework_rate", 0) or 0
    bug_ratio = bugs / max(throughput, 1)
    scores["quality"] = _clamp(100 - bug_ratio * 200 - rework * 100)

    # Flow: flow_efficiency + low WIP
    fe = metrics.get("flow_efficiency")
    if fe is not None:
        scores["flow"] = _clamp(fe * 100)
    else:
        scores["flow"] = 50.0

    # Reliability: low change_failure_rate + low MTTR
    cfr = metrics.get("change_failure_rate", 0) or 0
    mttr = metrics.get("mttr_hours", 0) or 0
    scores["reliability"] = _clamp(100 - cfr * 100 - min(mttr, 24) * 2)

    # Debt: inversely proportional to tech_debt_hours
    debt = metrics.get("tech_debt_hours", 0) or 0
    scores["debt"] = _clamp(100 - min(debt, 100))

    return scores


def _score_sales(metrics: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}

    # Revenue: quota attainment
    qa = metrics.get("quota_attainment")
    if qa is not None:
        scores["revenue"] = _clamp(qa * 100)
    else:
        scores["revenue"] = 50.0

    # Efficiency: shorter sales cycle is better (target: 30 days = 100)
    cycle = metrics.get("avg_sales_cycle_days", 30) or 30
    scores["efficiency"] = _clamp(100 - max(cycle - 30, 0) * 2)

    # Pipeline: pipeline_value vs revenue ratio
    pv = float(metrics.get("pipeline_value_pln", 0) or 0)
    rev = float(metrics.get("revenue_pln", 1) or 1)
    pipe_ratio = pv / max(rev, 1)
    scores["pipeline"] = _clamp(min(pipe_ratio * 33.3, 100))  # 3x pipeline = 100

    # Conversion
    cr = metrics.get("conversion_rate", 0) or 0
    scores["conversion"] = _clamp(cr * 100)

    return scores


def _score_customer_service(metrics: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}

    # Speed: first response time (target < 1h = 100)
    frt = metrics.get("avg_first_response_h", 1) or 1
    scores["speed"] = _clamp(100 - max(frt - 1, 0) * 10)

    # Quality: CSAT (5-point scale, 4.0+ = good)
    csat = metrics.get("csat_score")
    if csat is not None:
        scores["quality"] = _clamp(csat * 20)  # 5.0 -> 100
    else:
        scores["quality"] = 50.0

    # Resolution: FCR rate
    fcr = metrics.get("first_contact_resolution_rate", 0) or 0
    scores["resolution"] = _clamp(fcr * 100)

    # Escalation: lower is better
    esc = metrics.get("escalation_rate", 0) or 0
    scores["escalation"] = _clamp(100 - esc * 200)

    return scores


def _score_finance(metrics: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}

    # Budget: close to 0% variance is ideal
    var_pct = abs(metrics.get("budget_variance_pct", 0) or 0)
    scores["budget"] = _clamp(100 - var_pct * 5)

    # Margin
    margin = metrics.get("margin_pct", 0) or 0
    scores["margin"] = _clamp(margin)  # margin_pct directly as score

    # Efficiency: lower cost_per_unit is better (normalize to 100)
    cpu = metrics.get("cost_per_unit")
    if cpu is not None and cpu > 0:
        scores["efficiency"] = _clamp(100 / cpu * 10)
    else:
        scores["efficiency"] = 50.0

    return scores


def _score_operations(metrics: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}
    scores["throughput"] = _clamp(min((metrics.get("throughput", 0) or 0), 100))
    scores["quality"] = _clamp(100 - (metrics.get("error_rate", 0) or 0) * 100)
    scores["timeliness"] = _clamp(100 - (metrics.get("overdue_rate", 0) or 0) * 100)
    cpu = metrics.get("cost_per_unit")
    if cpu is not None and cpu > 0:
        scores["cost"] = _clamp(100 / cpu * 10)
    else:
        scores["cost"] = 50.0
    return scores


_SCORERS = {
    "engineering": _score_engineering,
    "sales": _score_sales,
    "customer_service": _score_customer_service,
    "finance": _score_finance,
    "operations": _score_operations,
}


# ---------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------

def _detect_anomalies(
    process_id: str,
    current_score: float,
    conn: psycopg.Connection,
) -> list[str]:
    """Compare current week to rolling 8-week history.

    Flags:
    - metric_anomaly: current > mean +/- 2*std
    - sustained_decline: 3+ consecutive weeks of score decline
    - sudden_drop: health drops >15pts in one week
    """
    flags: list[str] = []

    # Fetch last 8 weeks of health scores
    rows: list[dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT week_start, process_health_score
                FROM process_metrics
                WHERE process_id = %(pid)s
                  AND process_health_score IS NOT NULL
                ORDER BY week_start DESC
                LIMIT 8
                """,
                {"pid": process_id},
            )
            if cur.description:
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception as exc:
        logger.warning("process_collector.aggregator.anomaly_query_failed", error=str(exc))
        return flags

    if not rows:
        return flags

    historical_scores = [r["process_health_score"] for r in rows if r["process_health_score"] is not None]

    if len(historical_scores) >= 3:
        m = _mean(historical_scores)
        s = _std(historical_scores)
        if s > 0 and abs(current_score - m) > 2 * s:
            flags.append(f"metric_anomaly:health_score={current_score:.1f},mean={m:.1f},std={s:.1f}")

    # Sustained decline: 3+ consecutive weeks of decline
    if len(historical_scores) >= 3:
        # rows are DESC by week_start; prepend current score
        sequence = [current_score] + historical_scores
        decline_count = 0
        for i in range(len(sequence) - 1):
            if sequence[i] < sequence[i + 1]:
                decline_count += 1
            else:
                break
        if decline_count >= 3:
            flags.append(f"sustained_decline:weeks={decline_count}")

    # Sudden drop: >15 pts vs last week
    if historical_scores:
        last_score = historical_scores[0]
        drop = last_score - current_score
        if drop > 15:
            flags.append(f"sudden_drop:delta={drop:.1f}")

    return flags


# ---------------------------------------------------------------
# Public API
# ---------------------------------------------------------------

def calculate_process_health_score(
    metrics: dict[str, Any],
    process_type: str,
    conn: psycopg.Connection,
    process_id: str | None = None,
) -> tuple[float, list[str]]:
    """Calculate a 0-100 health score and anomaly flags.

    Args:
        metrics: collected metric dict (ProcessMetric field names).
        process_type: one of engineering/sales/customer_service/finance/operations.
        conn: database connection for historical lookups.
        process_id: UUID string for anomaly detection (optional).

    Returns:
        (health_score, anomaly_flags)
    """
    weights = _WEIGHTS.get(process_type, _WEIGHTS["operations"])
    scorer = _SCORERS.get(process_type, _score_operations)

    component_scores = scorer(metrics)

    # Weighted sum
    total = 0.0
    total_weight = 0.0
    for component, weight in weights.items():
        score = component_scores.get(component, 50.0)
        total += score * weight
        total_weight += weight

    health_score = _clamp(total / total_weight if total_weight > 0 else 50.0)

    # Anomaly detection
    anomaly_flags: list[str] = []
    if process_id:
        anomaly_flags = _detect_anomalies(process_id, health_score, conn)

    logger.info(
        "process_collector.aggregator.health_score",
        process_type=process_type,
        health_score=round(health_score, 2),
        components={k: round(v, 2) for k, v in component_scores.items()},
        anomalies=anomaly_flags,
    )

    return health_score, anomaly_flags
