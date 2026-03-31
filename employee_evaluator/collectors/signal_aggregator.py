"""Aggregate weekly signals into evaluation-period summaries."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from ..models import AggregatedSignals, RawSignal

log = structlog.get_logger("employee_evaluator.signal_aggregator")

# Fields that contribute to data_completeness calculation
_COMPLETENESS_FIELDS = [
    "teams_messages_sent",
    "emails_sent",
    "commits_count",
    "tasks_assigned",
    "docs_created",
    "hr_feedback_given",
]


def aggregate_signals(
    person_id: UUID,
    period_start: date,
    period_end: date,
    conn: psycopg.Connection,
) -> AggregatedSignals:
    """Read weekly signals and compute aggregated metrics for the period.

    Returns AggregatedSignals with averages, totals, trends, data_completeness.
    """
    raw_signals = _fetch_signals(person_id, period_start, period_end, conn)
    weeks_count = len(raw_signals)

    agg = AggregatedSignals(person_id=person_id, weeks_count=weeks_count)

    if weeks_count == 0:
        log.info("no_signals_found", person_id=str(person_id))
        return agg

    # ── Totals ───────────────────────────────────────────────────────
    agg.total_tasks_completed = sum(s.tasks_completed for s in raw_signals)
    agg.total_tasks_assigned = sum(s.tasks_assigned for s in raw_signals)
    agg.total_tasks_overdue = sum(s.tasks_overdue for s in raw_signals)
    agg.total_tasks_created = sum(s.tasks_created for s in raw_signals)
    agg.total_blockers_resolved = sum(s.tasks_blockers_resolved for s in raw_signals)
    agg.total_commits = sum(s.commits_count for s in raw_signals)
    agg.total_pr_reviews = sum(s.commits_pr_reviews for s in raw_signals)
    agg.total_docs_created = sum(s.docs_created for s in raw_signals)
    agg.total_docs_edited = sum(s.docs_edited for s in raw_signals)
    agg.total_feedback_given = sum(s.hr_feedback_given for s in raw_signals)
    agg.total_feedback_received = sum(s.hr_feedback_received for s in raw_signals)
    agg.total_training_hours = sum(s.hr_training_hours for s in raw_signals)
    agg.total_reactions_given = sum(s.teams_reactions_given for s in raw_signals)

    # ── Averages per week ────────────────────────────────────────────
    n = float(weeks_count)
    agg.avg_messages_sent = sum(s.teams_messages_sent for s in raw_signals) / n
    agg.avg_messages_received = sum(s.teams_messages_received for s in raw_signals) / n
    agg.avg_meetings_attended = sum(s.teams_meetings_attended for s in raw_signals) / n
    agg.avg_meetings_organized = sum(s.teams_meetings_organized for s in raw_signals) / n
    agg.avg_emails_sent = sum(s.emails_sent for s in raw_signals) / n
    agg.avg_emails_received = sum(s.emails_received for s in raw_signals) / n
    agg.avg_commits = agg.total_commits / n
    agg.avg_pr_reviews = agg.total_pr_reviews / n
    agg.avg_tasks_completed = agg.total_tasks_completed / n
    agg.avg_tasks_created = agg.total_tasks_created / n
    agg.avg_docs_created = agg.total_docs_created / n

    # Average response time (only from weeks with data)
    resp_hours = [s.emails_avg_response_hours for s in raw_signals if s.emails_avg_response_hours is not None]
    if resp_hours:
        agg.avg_response_hours = sum(resp_hours) / len(resp_hours)

    # ── Trends (compare first half vs second half) ───────────────────
    if weeks_count >= 4:
        mid = weeks_count // 2
        first_half = raw_signals[:mid]
        second_half = raw_signals[mid:]
        agg.trend_tasks_completed = _trend(first_half, second_half, "tasks_completed")
        agg.trend_messages_sent = _trend(first_half, second_half, "teams_messages_sent")
        agg.trend_commits = _trend(first_half, second_half, "commits_count")
        # For response hours, negative trend = improving (faster)
        agg.trend_response_hours = _trend_response(first_half, second_half)

    # ── Data completeness ────────────────────────────────────────────
    agg.data_completeness = _calc_completeness(raw_signals)

    log.info(
        "signals_aggregated",
        person_id=str(person_id),
        weeks=weeks_count,
        completeness=round(agg.data_completeness, 2),
    )
    return agg


def _fetch_signals(
    person_id: UUID,
    period_start: date,
    period_end: date,
    conn: psycopg.Connection,
) -> list[RawSignal]:
    """Fetch raw weekly signals ordered by week_start."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT * FROM employee_signals
               WHERE person_id = %s
                 AND week_start >= %s
                 AND week_start <= %s
               ORDER BY week_start""",
            (str(person_id), period_start, period_end),
        )
        rows = cur.fetchall()

    signals = []
    for row in rows:
        signals.append(RawSignal(
            person_id=row["person_id"],
            week_start=row["week_start"],
            teams_messages_sent=row.get("teams_messages_sent") or 0,
            teams_messages_received=row.get("teams_messages_received") or 0,
            teams_reactions_given=row.get("teams_reactions_given") or 0,
            teams_meetings_attended=row.get("teams_meetings_attended") or 0,
            teams_meetings_organized=row.get("teams_meetings_organized") or 0,
            emails_sent=row.get("emails_sent") or 0,
            emails_received=row.get("emails_received") or 0,
            emails_avg_response_hours=row.get("emails_avg_response_hours"),
            commits_count=row.get("commits_count") or 0,
            commits_lines_added=row.get("commits_lines_added") or 0,
            commits_lines_removed=row.get("commits_lines_removed") or 0,
            commits_pr_reviews=row.get("commits_pr_reviews") or 0,
            tasks_created=row.get("tasks_created") or 0,
            tasks_completed=row.get("tasks_completed") or 0,
            tasks_assigned=row.get("tasks_assigned") or 0,
            tasks_overdue=row.get("tasks_overdue") or 0,
            tasks_blockers_resolved=row.get("tasks_blockers_resolved") or 0,
            docs_created=row.get("docs_created") or 0,
            docs_edited=row.get("docs_edited") or 0,
            hr_absences_days=row.get("hr_absences_days") or 0,
            hr_training_hours=row.get("hr_training_hours") or 0,
            hr_feedback_given=row.get("hr_feedback_given") or 0,
            hr_feedback_received=row.get("hr_feedback_received") or 0,
        ))
    return signals


def _trend(
    first_half: list[RawSignal],
    second_half: list[RawSignal],
    attr: str,
) -> float:
    """Calculate trend as percentage change from first half to second half.

    Positive = improving, negative = declining.
    """
    avg_first = sum(getattr(s, attr) for s in first_half) / max(len(first_half), 1)
    avg_second = sum(getattr(s, attr) for s in second_half) / max(len(second_half), 1)
    if avg_first == 0:
        return 1.0 if avg_second > 0 else 0.0
    return (avg_second - avg_first) / avg_first


def _trend_response(
    first_half: list[RawSignal],
    second_half: list[RawSignal],
) -> float:
    """Response time trend. Negative value = faster (improving)."""
    vals_first = [s.emails_avg_response_hours for s in first_half if s.emails_avg_response_hours is not None]
    vals_second = [s.emails_avg_response_hours for s in second_half if s.emails_avg_response_hours is not None]
    if not vals_first or not vals_second:
        return 0.0
    avg_first = sum(vals_first) / len(vals_first)
    avg_second = sum(vals_second) / len(vals_second)
    if avg_first == 0:
        return 0.0
    return (avg_second - avg_first) / avg_first


def _calc_completeness(signals: list[RawSignal]) -> float:
    """Calculate data completeness as fraction of fields that have non-zero data."""
    if not signals:
        return 0.0
    field_scores = []
    for field_name in _COMPLETENESS_FIELDS:
        has_data = any(getattr(s, field_name, 0) > 0 for s in signals)
        field_scores.append(1.0 if has_data else 0.0)
    return sum(field_scores) / len(field_scores)
