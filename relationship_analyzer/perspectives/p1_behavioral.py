"""P1: Behavioral perspective — interaction volume, frequency, gaps, channels."""

from __future__ import annotations

from typing import Any

from ..models import PairData


def _safe_get(d: dict | None, key: str, default=None):
    if d is None:
        return default
    return d.get(key, default)


def compute_p1(pair_data: PairData, perspective: str) -> dict[str, Any]:
    """Compute behavioral metrics for a given perspective direction.

    perspective: 'a_to_b' or 'b_to_a'
    """
    if perspective == "a_to_b":
        rel = pair_data.rel_a_to_b
        beh_ego = pair_data.behavioral_a
        comm_ego = pair_data.comm_a
    else:
        rel = pair_data.rel_b_to_a
        beh_ego = pair_data.behavioral_b
        comm_ego = pair_data.comm_b

    # If no relationship record exists, try the reverse direction for some global stats
    interaction_count_total = _safe_get(rel, "interaction_count", 0)

    # Duration: from first_contact to now
    first_contact_at = _safe_get(rel, "first_contact_at")
    last_contact_at = _safe_get(rel, "last_contact_at")

    relationship_duration_days = None
    days_since_last_contact = None
    if first_contact_at and last_contact_at:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if hasattr(first_contact_at, "tzinfo"):
            relationship_duration_days = max(1, (now - first_contact_at).days)
        if hasattr(last_contact_at, "tzinfo"):
            days_since_last_contact = max(0, (now - last_contact_at).days)

    # Interactions per period — use behavioral table if available
    interactions_30d = _safe_get(beh_ego, "interactions_last_30d") if beh_ego else None

    # Approximate 90d as total (behavioral only has 30d and 7d)
    # Best estimate: if we have the pair interaction_count and duration, use it
    interaction_count_90d = None
    if interaction_count_total and relationship_duration_days:
        if relationship_duration_days <= 90:
            interaction_count_90d = interaction_count_total
        else:
            # Proportional estimate
            interaction_count_90d = int(interaction_count_total * 90 / relationship_duration_days)

    # Average interactions per week
    avg_interactions_per_week = None
    if interaction_count_total and relationship_duration_days and relationship_duration_days > 0:
        weeks = relationship_duration_days / 7.0
        avg_interactions_per_week = round(interaction_count_total / weeks, 2) if weeks > 0 else None

    # Channel info
    active_channels_count = _safe_get(beh_ego, "active_channels_count")
    dominant_channel = _safe_get(rel, "dominant_channel")

    # Message length (from communication pattern)
    avg_message_length_chars = _safe_get(comm_ego, "avg_message_length")

    # Response times
    response_time_avg_minutes = _safe_get(comm_ego, "avg_response_time_min")
    # P90 not directly available — approximate as 2x avg if avg exists
    response_time_p90_minutes = None
    if response_time_avg_minutes is not None:
        response_time_p90_minutes = round(response_time_avg_minutes * 2.0, 1)

    # Longest gap: not directly stored, use days_since_last_contact as proxy
    longest_gap_days = days_since_last_contact

    return {
        "interaction_count_total": interaction_count_total,
        "interaction_count_30d": interactions_30d,
        "interaction_count_90d": interaction_count_90d,
        "avg_interactions_per_week": avg_interactions_per_week,
        "days_since_last_contact": days_since_last_contact,
        "longest_gap_days": longest_gap_days,
        "relationship_duration_days": relationship_duration_days,
        "active_channels_count": active_channels_count,
        "dominant_channel": dominant_channel,
        "avg_message_length_chars": avg_message_length_chars,
        "response_time_avg_minutes": float(response_time_avg_minutes) if response_time_avg_minutes is not None else None,
        "response_time_p90_minutes": response_time_p90_minutes,
    }
