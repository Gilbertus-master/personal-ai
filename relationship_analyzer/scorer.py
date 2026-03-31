"""Health score calculator for relationship analyses.

Computes a 0-100 score from 6 weighted sub-scores:
  S1 Activity    (0.25) — interaction volume & recency
  S2 Reciprocity (0.20) — balance in communication
  S3 Emotion     (0.20) — sentiment quality
  S4 Trajectory  (0.15) — relationship direction
  S5 Depth       (0.10) — topic richness & discussion depth
  S6 Context     (0.10) — shared history & open loops

Labels: >=75 excellent, >=55 good, >=35 fair, >=15 poor, <15 at_risk
"""

from __future__ import annotations

import math
from typing import Any

WEIGHTS = {
    "activity": 0.25,
    "reciprocity": 0.20,
    "emotion": 0.20,
    "trajectory": 0.15,
    "depth": 0.10,
    "context": 0.10,
}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _score_activity(p: dict[str, Any]) -> float:
    """S1: Activity score from P1 behavioral data. Returns 0-1."""
    components = []

    # Interaction volume: log scale, cap at ~200 interactions
    total = p.get("interaction_count_total")
    if total is not None and total > 0:
        components.append(_clamp(math.log(total + 1) / math.log(201)))

    # Recency: inverse of days since last contact
    days_since = p.get("days_since_last_contact")
    if days_since is not None:
        # 0 days = 1.0, 30 days = 0.5, 180 days = ~0.1
        components.append(_clamp(math.exp(-0.02 * days_since)))

    # Frequency: avg interactions per week
    avg_per_week = p.get("avg_interactions_per_week")
    if avg_per_week is not None:
        # 1/week = 0.5, 5/week = 0.9, <0.1/week = 0.1
        components.append(_clamp(1.0 - math.exp(-0.5 * avg_per_week)))

    # Channel diversity
    channels = p.get("active_channels_count")
    if channels is not None:
        components.append(_clamp(min(int(channels), 5) / 5.0))

    if not components:
        return 0.0
    return sum(components) / len(components)


def _score_reciprocity(p: dict[str, Any]) -> float:
    """S2: Reciprocity score from P2 asymmetry data. Returns 0-1."""
    components = []

    # Initiation balance: 0.5 is perfect
    init_ratio = p.get("initiation_ratio")
    if init_ratio is not None:
        balance = 1.0 - 2.0 * abs(float(init_ratio) - 0.5)
        components.append(_clamp(balance))

    # Response rate
    rr = p.get("response_rate")
    if rr is not None:
        components.append(_clamp(float(rr)))

    # Lag asymmetry: 0 is perfect balance
    lag_asym = p.get("lag_asymmetry")
    if lag_asym is not None:
        components.append(_clamp(1.0 - abs(float(lag_asym))))

    # Formality alignment
    form_asym = p.get("formality_asymmetry")
    if form_asym is not None:
        components.append(_clamp(1.0 - abs(float(form_asym))))

    if not components:
        return 0.0
    return sum(components) / len(components)


def _score_emotion(p: dict[str, Any]) -> float:
    """S3: Emotion score from P3 sentiment data. Returns 0-1."""
    components = []

    # Average sentiment ego: map [-1, 1] -> [0, 1]
    sent_ego = p.get("avg_sentiment_ego")
    if sent_ego is not None:
        components.append(_clamp((float(sent_ego) + 1.0) / 2.0))

    # Emotional support
    ess = p.get("emotional_support_score")
    if ess is not None:
        components.append(_clamp(float(ess)))

    # Conflict penalty
    if p.get("conflict_detected"):
        components.append(0.0)

    # Positive to negative ratio
    pos = p.get("positive_signal_count")
    neg = p.get("negative_signal_count")
    if pos is not None and neg is not None:
        total_signals = (pos or 0) + (neg or 0)
        if total_signals > 0:
            components.append(_clamp((pos or 0) / total_signals))

    if not components:
        return 0.5  # Neutral default
    return sum(components) / len(components)


def _score_trajectory(p: dict[str, Any]) -> float:
    """S4: Trajectory score from P5 trajectory data. Returns 0-1."""
    components = []

    # Current tie strength: direct map 0-1
    ts = p.get("tie_strength_current")
    if ts is not None:
        components.append(_clamp(float(ts)))

    # 30d delta: positive = improving
    d30 = p.get("tie_strength_delta_30d")
    if d30 is not None:
        # Map [-0.5, 0.5] -> [0, 1]
        components.append(_clamp(float(d30) + 0.5))

    # Lifecycle stage bonuses
    stage = p.get("lifecycle_stage", "")
    stage_scores = {
        "close": 1.0,
        "established": 0.75,
        "developing": 0.6,
        "new": 0.5,
        "acquaintance": 0.3,
        "fading": 0.15,
        "dormant": 0.05,
    }
    if stage in stage_scores:
        components.append(stage_scores[stage])

    if not components:
        return 0.3
    return sum(components) / len(components)


def _score_depth(p: dict[str, Any]) -> float:
    """S5: Depth score from P4 topics data. Returns 0-1."""
    components = []

    # Number of shared entities
    shared = p.get("shared_entities_count")
    if shared is not None:
        # Log scale: 1 entity = 0.3, 5 = 0.6, 20+ = 1.0
        components.append(_clamp(math.log(int(shared) + 1) / math.log(21)))

    # Discussion depth
    depth = p.get("discussion_depth_score")
    if depth is not None:
        components.append(_clamp(float(depth)))

    # Number of topics discussed
    topics = p.get("top_topics")
    if topics and isinstance(topics, list):
        # 1 topic = 0.2, 5 = 0.5, 15 = 1.0
        components.append(_clamp(len(topics) / 15.0))

    if not components:
        return 0.0
    return sum(components) / len(components)


def _score_context(p: dict[str, Any]) -> float:
    """S6: Context score from P7 context data. Returns 0-1."""
    components = []

    # Shared contacts
    sc = p.get("shared_contacts_count")
    if sc is not None:
        components.append(_clamp(math.log(int(sc) + 1) / math.log(21)))

    # Open loops (having some = engaged, too many = risk)
    ol = p.get("open_loops_count")
    if ol is not None:
        ol = int(ol)
        if ol == 0:
            components.append(0.3)
        elif ol <= 3:
            components.append(0.8)
        elif ol <= 7:
            components.append(0.6)
        else:
            components.append(0.4)  # Too many open loops

    # Shared experiences
    se = p.get("shared_experiences_count")
    if se is not None:
        components.append(_clamp(min(int(se), 10) / 10.0))

    # Milestones
    mc = p.get("milestone_count")
    if mc is not None:
        components.append(_clamp(min(int(mc), 5) / 5.0))

    if not components:
        return 0.0
    return sum(components) / len(components)


def calculate_health_score(perspectives: dict[str, Any]) -> tuple[int, str]:
    """Calculate overall relationship health score.

    Args:
        perspectives: Merged dict of all perspective fields (dyadic view).

    Returns:
        Tuple of (score 0-100, label).
    """
    sub_scores = {
        "activity": _score_activity(perspectives),
        "reciprocity": _score_reciprocity(perspectives),
        "emotion": _score_emotion(perspectives),
        "trajectory": _score_trajectory(perspectives),
        "depth": _score_depth(perspectives),
        "context": _score_context(perspectives),
    }

    weighted = sum(sub_scores[k] * WEIGHTS[k] for k in WEIGHTS)
    score = int(round(weighted * 100))
    score = max(0, min(100, score))

    if score >= 75:
        label = "excellent"
    elif score >= 55:
        label = "good"
    elif score >= 35:
        label = "fair"
    elif score >= 15:
        label = "poor"
    else:
        label = "at_risk"

    return score, label
