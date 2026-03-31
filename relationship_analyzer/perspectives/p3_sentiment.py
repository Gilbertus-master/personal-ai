"""P3: Sentiment perspective — emotional tone, trends, conflict signals."""

from __future__ import annotations

from typing import Any

from ..models import PairData


def _safe_get(d: dict | None, key: str, default=None):
    if d is None:
        return default
    return d.get(key, default)


def compute_p3(pair_data: PairData, perspective: str) -> dict[str, Any]:
    """Compute sentiment metrics.

    Uses dim_sentiment from person_relationships and avg_sentiment from
    person_psychographic as proxies.
    """
    if perspective == "a_to_b":
        rel = pair_data.rel_a_to_b
        psycho_ego = pair_data.psycho_a
        psycho_alter = pair_data.psycho_b
        traj = pair_data.trajectory_a_to_b
    else:
        rel = pair_data.rel_b_to_a
        psycho_ego = pair_data.psycho_b
        psycho_alter = pair_data.psycho_a
        traj = pair_data.trajectory_b_to_a

    # Average sentiment per person (from psychographic profile)
    avg_sentiment_ego = _safe_get(psycho_ego, "avg_sentiment")
    avg_sentiment_alter = _safe_get(psycho_alter, "avg_sentiment")

    # Sentiment variance
    sentiment_variance_ego = _safe_get(psycho_ego, "sentiment_variance")

    # Sentiment trend: use trajectory delta_30d as a proxy
    # Positive delta = relationship improving = positive sentiment trend
    sentiment_trend = None
    if traj is not None:
        delta_30d = _safe_get(traj, "delta_30d")
        if delta_30d is not None:
            sentiment_trend = round(float(delta_30d), 3)

    # dim_sentiment from the relationship as overall emotional quality
    dim_sentiment = _safe_get(rel, "dim_sentiment", 0.0)

    # Estimate positive/negative signal counts from sentiment values
    positive_signal_count = None
    negative_signal_count = None
    interaction_count = _safe_get(rel, "interaction_count", 0)
    if avg_sentiment_ego is not None and interaction_count > 0:
        # Map sentiment [-1, 1] to a ratio of positive interactions
        pos_ratio = max(0.0, min(1.0, (float(avg_sentiment_ego) + 1.0) / 2.0))
        positive_signal_count = int(interaction_count * pos_ratio)
        negative_signal_count = interaction_count - positive_signal_count

    # Emotional support score: composite of sentiment + reciprocity
    emotional_support_score = None
    if dim_sentiment is not None:
        reciprocity = _safe_get(rel, "dim_reciprocity", 0.0)
        # Average of sentiment quality and reciprocity
        emotional_support_score = round(
            (max(0.0, (float(dim_sentiment) + 1.0) / 2.0) + float(reciprocity or 0)) / 2.0, 3
        )

    # Conflict detection: negative sentiment below threshold
    conflict_detected = False
    conflict_last_detected_at = None
    if dim_sentiment is not None and float(dim_sentiment) < -0.3:
        conflict_detected = True
        # Use last_contact_at as proxy for when conflict was last detected
        conflict_last_detected_at = _safe_get(rel, "last_contact_at")

    return {
        "avg_sentiment_ego": float(avg_sentiment_ego) if avg_sentiment_ego is not None else None,
        "avg_sentiment_alter": float(avg_sentiment_alter) if avg_sentiment_alter is not None else None,
        "sentiment_variance_ego": float(sentiment_variance_ego) if sentiment_variance_ego is not None else None,
        "sentiment_trend": sentiment_trend,
        "positive_signal_count": positive_signal_count,
        "negative_signal_count": negative_signal_count,
        "emotional_support_score": emotional_support_score,
        "conflict_detected": conflict_detected,
        "conflict_last_detected_at": conflict_last_detected_at,
    }
