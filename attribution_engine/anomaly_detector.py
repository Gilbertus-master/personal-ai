"""Anomaly detection for process metrics.

Compares current-week metrics against a rolling 8-week baseline and flags
deviations beyond 1.5 sigma, sustained declines (3+ weeks), and sudden drops
(>15 pts in one week).
"""

from __future__ import annotations

import math
from uuid import UUID

import structlog
from psycopg import Connection

from .models import AnomalySignal

log = structlog.get_logger("attribution_engine.anomaly_detector")

# Metrics we track from process_metrics
TRACKED_METRICS = [
    "health_score",
    "throughput",
    "avg_cycle_time_hours",
    "overdue_rate",
    "error_rate",
    "rework_rate",
    "escalation_rate",
    "csat_score",
]

SIGMA_THRESHOLD = 1.5
SUDDEN_DROP_THRESHOLD = 15.0
SUSTAINED_DECLINE_WEEKS = 3


def _fetch_metric_history(
    process_id: UUID, metric_name: str, weeks: int, conn: Connection
) -> list[tuple[float, str]]:
    """Fetch last N weeks of a single metric, ordered oldest-first.

    Returns list of (value, week_start_str).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT week_start, {metric}
            FROM process_metrics
            WHERE process_id = %s
              AND {metric} IS NOT NULL
            ORDER BY week_start DESC
            LIMIT %s
            """.format(metric=metric_name),
            (str(process_id), weeks),
        )
        rows = cur.fetchall()
    # reverse to oldest-first
    return [(float(r[1]), str(r[0])) for r in reversed(rows)]


def _compute_baseline(values: list[float]) -> tuple[float, float]:
    """Return (mean, stddev) of values, excluding the last one (current)."""
    if len(values) < 2:
        return values[0] if values else 0.0, 0.0
    baseline = values[:-1]
    n = len(baseline)
    mean = sum(baseline) / n
    variance = sum((v - mean) ** 2 for v in baseline) / n
    stddev = math.sqrt(variance) if variance > 0 else 0.0
    return mean, stddev


def _detect_sustained_decline(values: list[float], metric_name: str) -> int:
    """Count consecutive declining weeks from the tail end.

    For metrics where lower is better (overdue_rate, error_rate, etc.),
    'decline' means increasing values.
    """
    inverted = metric_name in (
        "overdue_rate", "error_rate", "rework_rate",
        "escalation_rate", "avg_cycle_time_hours",
    )
    if len(values) < 2:
        return 0
    streak = 0
    for i in range(len(values) - 1, 0, -1):
        if inverted:
            declining = values[i] > values[i - 1]
        else:
            declining = values[i] < values[i - 1]
        if declining:
            streak += 1
        else:
            break
    return streak


def detect_anomalies(
    process_id: UUID,
    current_metrics: dict | None,
    conn: Connection,
) -> list[AnomalySignal]:
    """Detect anomalies for a process by comparing current week to 8-week rolling baseline.

    Args:
        process_id: The process UUID.
        current_metrics: Optional dict of current-week metric values. If None,
            the latest row from process_metrics is used.
        conn: Active psycopg Connection.

    Returns:
        List of AnomalySignal objects.
    """
    anomalies: list[AnomalySignal] = []

    for metric in TRACKED_METRICS:
        history = _fetch_metric_history(process_id, metric, weeks=9, conn=conn)
        if len(history) < 2:
            continue

        values = [v for v, _ in history]
        current = values[-1]

        if current_metrics and metric in current_metrics:
            current = float(current_metrics[metric])

        baseline_mean, baseline_std = _compute_baseline(values)

        # Sigma deviation
        if baseline_std > 0:
            sigma = abs(current - baseline_mean) / baseline_std
        else:
            sigma = 0.0

        # Determine direction of the anomaly
        inverted = metric in (
            "overdue_rate", "error_rate", "rework_rate",
            "escalation_rate", "avg_cycle_time_hours",
        )
        if sigma >= SIGMA_THRESHOLD:
            if inverted:
                direction = "problem" if current > baseline_mean else "success"
            else:
                direction = "problem" if current < baseline_mean else "success"

            anomaly = AnomalySignal(
                metric_name=metric,
                current_value=current,
                baseline_value=round(baseline_mean, 2),
                sigma_deviation=round(sigma, 2),
                direction=direction,
                anomaly_type="deviation",
            )
            anomalies.append(anomaly)
            log.info(
                "anomaly_detected",
                process_id=str(process_id),
                metric=metric,
                sigma=round(sigma, 2),
                direction=direction,
            )

        # Sudden drop (>15 pts single week)
        if len(values) >= 2:
            delta = current - values[-2]
            if inverted:
                is_sudden = delta > SUDDEN_DROP_THRESHOLD
            else:
                is_sudden = delta < -SUDDEN_DROP_THRESHOLD

            if is_sudden:
                anomalies.append(AnomalySignal(
                    metric_name=metric,
                    current_value=current,
                    baseline_value=values[-2],
                    sigma_deviation=round(sigma, 2),
                    direction="problem",
                    anomaly_type="sudden_drop",
                ))

        # Sustained decline
        weeks_declining = _detect_sustained_decline(values, metric)
        if weeks_declining >= SUSTAINED_DECLINE_WEEKS:
            # Only add if we haven't already flagged this metric as deviation
            already_flagged = any(
                a.metric_name == metric and a.anomaly_type != "sustained_decline"
                for a in anomalies
            )
            if not already_flagged:
                anomalies.append(AnomalySignal(
                    metric_name=metric,
                    current_value=current,
                    baseline_value=round(baseline_mean, 2),
                    sigma_deviation=round(sigma, 2),
                    direction="problem",
                    anomaly_type="sustained_decline",
                    weeks_declining=weeks_declining,
                ))
            else:
                # Update existing signal with decline info
                for a in anomalies:
                    if a.metric_name == metric:
                        a.weeks_declining = weeks_declining
                        if weeks_declining >= SUSTAINED_DECLINE_WEEKS:
                            a.anomaly_type = "sustained_decline"
                        break

    log.info(
        "anomaly_detection_complete",
        process_id=str(process_id),
        anomaly_count=len(anomalies),
    )
    return anomalies
