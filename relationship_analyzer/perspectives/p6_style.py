"""P6: Style perspective — communication style match, humor, questions, accommodation."""

from __future__ import annotations

from typing import Any

from ..models import PairData


def _safe_get(d: dict | None, key: str, default=None):
    if d is None:
        return default
    return d.get(key, default)


def compute_p6(pair_data: PairData, perspective: str) -> dict[str, Any]:
    """Compute communication style metrics.

    Uses person_communication_pattern and person_psychographic for style signals.
    """
    if perspective == "a_to_b":
        comm_ego = pair_data.comm_a
        comm_alter = pair_data.comm_b
        psycho_ego = pair_data.psycho_a
        psycho_alter = pair_data.psycho_b
    else:
        comm_ego = pair_data.comm_b
        comm_alter = pair_data.comm_a
        psycho_ego = pair_data.psycho_b
        psycho_alter = pair_data.psycho_a

    # Question ratio (from communication pattern)
    question_ratio_ego = _safe_get(comm_ego, "question_ratio")
    question_ratio_ego = float(question_ratio_ego) if question_ratio_ego is not None else None

    # Personal question ratio: not directly stored, estimate from question_ratio * extraversion
    personal_question_ratio = None
    if question_ratio_ego is not None:
        extraversion = _safe_get(psycho_ego, "big5_extraversion")
        if extraversion is not None:
            personal_question_ratio = round(question_ratio_ego * float(extraversion), 3)

    # Humor signal ratio: not directly stored, estimate from communication_style
    # If style contains humor-related keywords, set a baseline ratio
    humor_signal_ratio = None
    ego_style = _safe_get(comm_ego, "message_style")
    if ego_style and isinstance(ego_style, str):
        humor_keywords = ("humor", "casual", "witty", "fun", "playful", "lekki")
        if any(kw in ego_style.lower() for kw in humor_keywords):
            humor_signal_ratio = 0.15
        else:
            humor_signal_ratio = 0.03

    # Language accommodation: 1 - abs(formality_ego - formality_alter)
    formality_ego = _safe_get(comm_ego, "formality_score")
    formality_alter = _safe_get(comm_alter, "formality_score")
    language_accommodation = None
    if formality_ego is not None and formality_alter is not None:
        language_accommodation = round(
            1.0 - abs(float(formality_ego) - float(formality_alter)), 3
        )

    # Emotional language ratio: proxy from neuroticism + extraversion
    emotional_language_ratio = None
    neuroticism = _safe_get(psycho_ego, "big5_neuroticism")
    extraversion = _safe_get(psycho_ego, "big5_extraversion")
    if neuroticism is not None and extraversion is not None:
        emotional_language_ratio = round(
            (float(neuroticism) + float(extraversion)) / 2.0, 3
        )

    # Support language ratio: proxy from agreeableness
    support_language_ratio = None
    agreeableness = _safe_get(psycho_ego, "big5_agreeableness")
    if agreeableness is not None:
        support_language_ratio = round(float(agreeableness), 3)

    # Communication style match: composite of formality match + message_style similarity
    communication_style_match = None
    match_components = []

    if language_accommodation is not None:
        match_components.append(language_accommodation)

    # Style match: compare communication_style from psychographic
    ego_comm_style = _safe_get(psycho_ego, "communication_style")
    alter_comm_style = _safe_get(psycho_alter, "communication_style")
    if ego_comm_style and alter_comm_style:
        if ego_comm_style == alter_comm_style:
            match_components.append(1.0)
        else:
            match_components.append(0.4)

    # Message length similarity
    ego_msg_len = _safe_get(comm_ego, "avg_message_length")
    alter_msg_len = _safe_get(comm_alter, "avg_message_length")
    if ego_msg_len is not None and alter_msg_len is not None:
        max_len = max(int(ego_msg_len), int(alter_msg_len), 1)
        min_len = min(int(ego_msg_len), int(alter_msg_len))
        match_components.append(round(min_len / max_len, 3))

    if match_components:
        communication_style_match = round(
            sum(match_components) / len(match_components), 3
        )

    return {
        "humor_signal_ratio": humor_signal_ratio,
        "question_ratio_ego": question_ratio_ego,
        "personal_question_ratio": personal_question_ratio,
        "language_accommodation": language_accommodation,
        "emotional_language_ratio": emotional_language_ratio,
        "support_language_ratio": support_language_ratio,
        "communication_style_match": communication_style_match,
    }
