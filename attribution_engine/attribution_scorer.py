"""Attribution scoring algorithm.

Determines causal attribution for process health signals:
- Process-inherent issues
- People-driven issues
- Interaction/collaboration issues
- External factors
- Unknown
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import structlog
from psycopg import Connection

from .models import AnomalySignal, AttributionResult

log = structlog.get_logger("attribution_engine.attribution_scorer")

MIN_WEEKS_FOR_ATTRIBUTION = 4


def _normalize_attributions(result: AttributionResult) -> AttributionResult:
    """Normalize all attribution factors to sum to 1.0."""
    total = (
        result.attribution_process
        + result.attribution_people
        + result.attribution_interaction
        + result.attribution_external
        + result.attribution_unknown
    )
    if total <= 0:
        result.attribution_unknown = 1.0
        return result

    result.attribution_process = round(result.attribution_process / total, 3)
    result.attribution_people = round(result.attribution_people / total, 3)
    result.attribution_interaction = round(result.attribution_interaction / total, 3)
    result.attribution_external = round(result.attribution_external / total, 3)
    result.attribution_unknown = round(result.attribution_unknown / total, 3)

    # Fix rounding to ensure exactly 1.0
    remainder = 1.0 - (
        result.attribution_process
        + result.attribution_people
        + result.attribution_interaction
        + result.attribution_external
        + result.attribution_unknown
    )
    result.attribution_unknown = round(result.attribution_unknown + remainder, 3)

    return result


def _determine_severity(health_score: float | None) -> str:
    """Determine severity based on current health score."""
    if health_score is None:
        return "medium"
    if health_score < 25:
        return "critical"
    if health_score < 40:
        return "high"
    if health_score < 55:
        return "medium"
    return "low"


def _determine_direction(anomalies: list[AnomalySignal]) -> str:
    """Determine overall direction from anomaly signals."""
    problems = sum(1 for a in anomalies if a.direction == "problem")
    successes = sum(1 for a in anomalies if a.direction == "success")
    if problems > successes:
        return "problem"
    if successes > problems:
        return "success"
    return "neutral"


def _analyze_process_signals(
    anomalies: list[AnomalySignal],
    process_signals: dict,
) -> float:
    """Score process-inherent attribution.

    If anomalies affect metrics regardless of people changes,
    the issue is likely process-inherent.
    """
    score = 0.0

    # Structural process issues: multiple metric categories affected simultaneously
    affected_metrics = {a.metric_name for a in anomalies}
    structural_metrics = {"avg_cycle_time_hours", "rework_rate", "error_rate"}
    if len(affected_metrics & structural_metrics) >= 2:
        score += 0.3

    # Sustained decline suggests systemic issue
    sustained = [a for a in anomalies if a.anomaly_type == "sustained_decline"]
    if sustained:
        score += 0.2 * min(len(sustained), 3)

    # Health below baseline by large margin
    current_health = process_signals.get("current_health")
    baseline_health = process_signals.get("baseline_health")
    if current_health is not None and baseline_health is not None:
        gap = baseline_health - current_health
        if gap > 20:
            score += 0.2
        elif gap > 10:
            score += 0.1

    return min(score, 0.8)


def _analyze_people_signals(
    people_signals: dict,
) -> float:
    """Score people-driven attribution.

    Checks flight risk, delivery scores, trajectory, and open loops.
    """
    score = 0.0

    avg_flight_risk = people_signals.get("avg_flight_risk", 0.0)
    avg_delivery = people_signals.get("avg_delivery_score", 3.0)
    avg_open_loops = people_signals.get("avg_open_loops", 0.0)
    trajectories_cooling = people_signals.get("trajectory_signals", [])

    # High flight risk
    if avg_flight_risk > 0.6:
        score += 0.3
    elif avg_flight_risk > 0.4:
        score += 0.15

    # Low delivery
    if avg_delivery < 2.5:
        score += 0.2
    elif avg_delivery < 3.0:
        score += 0.1

    # Cooling trajectories
    if trajectories_cooling:
        score += 0.15 * min(len(trajectories_cooling), 2)

    # High open loops
    if avg_open_loops > 3:
        score += 0.1
    elif avg_open_loops > 2:
        score += 0.05

    return min(score, 0.8)


def _analyze_interaction_signals(
    people_signals: dict,
) -> float:
    """Score interaction/collaboration attribution.

    Checks if specific people consistently underperform vs team average.
    """
    score = 0.0
    participants = people_signals.get("participants", [])
    if not participants:
        return score

    overdue_ratios = [p["overdue_ratio"] for p in participants if p["tasks_owned"] > 0]
    if not overdue_ratios:
        return score

    team_avg_overdue = sum(overdue_ratios) / len(overdue_ratios) if overdue_ratios else 0

    # Check for individual outliers: person with 2x the team average overdue rate
    outliers = [
        p for p in participants
        if p["tasks_owned"] > 0
        and team_avg_overdue > 0
        and p["overdue_ratio"] >= 2 * team_avg_overdue
    ]
    if outliers:
        score += 0.4 * min(len(outliers) / len(participants), 1.0)

    # Check for delivery score variance (collaboration friction)
    delivery_scores = [p["delivery_score"] for p in participants if p["delivery_score"] > 0]
    if len(delivery_scores) >= 2:
        mean_d = sum(delivery_scores) / len(delivery_scores)
        variance = sum((d - mean_d) ** 2 for d in delivery_scores) / len(delivery_scores)
        if variance > 1.5:
            score += 0.2

    return min(score, 0.7)


def _compute_confidence(data_points: int, weeks: int) -> float:
    """Compute confidence score based on data availability."""
    if weeks < MIN_WEEKS_FOR_ATTRIBUTION:
        return 0.1
    weeks_factor = min(weeks / 12.0, 1.0)
    data_factor = min(data_points / 50.0, 1.0)
    return round(0.5 * weeks_factor + 0.5 * data_factor, 2)


def _build_top_people(participants: list[dict], direction: str) -> tuple[list[dict], list[dict]]:
    """Build top_people_positive and top_people_negative lists."""
    positive = []
    negative = []

    for p in participants:
        entry = {
            "person_id": p["person_id"],
            "person_name": p["person_name"],
            "role": p.get("role"),
            "overdue_ratio": p["overdue_ratio"],
            "flight_risk": p["flight_risk"],
            "delivery_score": p["delivery_score"],
        }
        # Score: lower overdue + higher delivery + lower flight_risk = more positive
        impact = (1 - p["overdue_ratio"]) * 0.4 + (p["delivery_score"] / 5) * 0.4 + (1 - p["flight_risk"]) * 0.2
        entry["impact_score"] = round(impact, 3)

        if impact >= 0.6:
            positive.append(entry)
        elif impact < 0.4:
            negative.append(entry)

    positive.sort(key=lambda x: x["impact_score"], reverse=True)
    negative.sort(key=lambda x: x["impact_score"])

    return positive[:5], negative[:5]


def calculate_attribution(
    process_id: UUID,
    week_start: date,
    anomalies: list[AnomalySignal],
    people_signals: dict,
    process_signals: dict,
    conn: Connection,
) -> AttributionResult:
    """Calculate causal attribution for a process-week pair.

    Algorithm:
    1. If <4 weeks data: attribution_unknown=1.0
    2. If no anomalies: direction='neutral'
    3. Analyze process, people, interaction signals
    4. Normalize to sum=1.0
    5. Set severity and confidence
    """
    weeks_data = process_signals.get("weeks_data", 0)
    participants = people_signals.get("participants", [])
    data_points = weeks_data * max(len(participants), 1)

    result = AttributionResult(
        process_id=process_id,
        week_start=week_start,
        data_points_count=data_points,
        min_weeks_data=weeks_data,
        process_signals=process_signals,
        people_signals=people_signals,
    )

    # Fetch team_id
    with conn.cursor() as cur:
        cur.execute(
            "SELECT department FROM processes WHERE process_id = %s",
            (str(process_id),),
        )
        row = cur.fetchone()
        if row and row[0]:
            result.team_id = str(row[0])

    # Rule 1: insufficient data
    if weeks_data < MIN_WEEKS_FOR_ATTRIBUTION:
        result.attribution_unknown = 1.0
        result.confidence = 0.1
        result.direction = "neutral"
        log.info("insufficient_data", process_id=str(process_id), weeks=weeks_data)
        return result

    # Rule 2: no anomalies
    if not anomalies:
        result.direction = "neutral"
        result.attribution_unknown = 1.0
        result.confidence = _compute_confidence(data_points, weeks_data)
        return result

    # Rule 3-5: analyze signals
    result.direction = _determine_direction(anomalies)

    result.attribution_process = _analyze_process_signals(anomalies, process_signals)
    result.attribution_people = _analyze_people_signals(people_signals)
    result.attribution_interaction = _analyze_interaction_signals(people_signals)

    # External: placeholder (requires external data feeds)
    result.attribution_external = 0.0

    # Remainder goes to unknown
    assigned = (
        result.attribution_process
        + result.attribution_people
        + result.attribution_interaction
        + result.attribution_external
    )
    result.attribution_unknown = max(0.0, 1.0 - assigned)

    # Normalize
    result = _normalize_attributions(result)

    # Severity
    current_health = process_signals.get("current_health")
    result.severity = _determine_severity(current_health)

    # Confidence
    result.confidence = _compute_confidence(data_points, weeks_data)

    # Top people
    top_pos, top_neg = _build_top_people(participants, result.direction)
    result.top_people_positive = top_pos
    result.top_people_negative = top_neg

    # Interaction signals
    result.interaction_signals = {
        "anomalies": [a.model_dump() for a in anomalies],
        "anomaly_count": len(anomalies),
        "problem_anomalies": sum(1 for a in anomalies if a.direction == "problem"),
        "success_anomalies": sum(1 for a in anomalies if a.direction == "success"),
    }

    log.info(
        "attribution_calculated",
        process_id=str(process_id),
        direction=result.direction,
        severity=result.severity,
        confidence=result.confidence,
        process_attr=result.attribution_process,
        people_attr=result.attribution_people,
        interaction_attr=result.attribution_interaction,
    )

    return result
