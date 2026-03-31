"""Competency weighting framework and overall score calculation."""

from __future__ import annotations

from typing import Any

import structlog

from ..config import (
    LABEL_BELOW,
    LABEL_DEVELOPING,
    LABEL_EXCEPTIONAL,
    LABEL_EXCEEDS,
    LABEL_MEETS,
)
from ..models import CompetencyScore

log = structlog.get_logger("employee_evaluator.framework")

# Default weights (must sum to 1.0)
DEFAULT_WEIGHTS: dict[str, float] = {
    "delivery": 0.20,
    "collaboration": 0.15,
    "communication": 0.10,
    "initiative": 0.10,
    "knowledge": 0.10,
    "leadership": 0.10,
    "growth": 0.10,
    "relationships": 0.15,
}


def get_competency_weights(role_config: dict[str, Any] | None = None) -> dict[str, float]:
    """Get competency weights from role_config or defaults.

    Args:
        role_config: Row from role_configs table with w_* columns.

    Returns:
        dict mapping competency name to weight (summing to ~1.0).
    """
    if not role_config:
        return DEFAULT_WEIGHTS.copy()

    weights = {
        "delivery": role_config.get("w_delivery", DEFAULT_WEIGHTS["delivery"]),
        "collaboration": role_config.get("w_collaboration", DEFAULT_WEIGHTS["collaboration"]),
        "communication": role_config.get("w_communication", DEFAULT_WEIGHTS["communication"]),
        "initiative": role_config.get("w_initiative", DEFAULT_WEIGHTS["initiative"]),
        "knowledge": role_config.get("w_knowledge", DEFAULT_WEIGHTS["knowledge"]),
        "leadership": role_config.get("w_leadership", DEFAULT_WEIGHTS["leadership"]),
        "growth": role_config.get("w_growth", DEFAULT_WEIGHTS["growth"]),
        "relationships": role_config.get("w_relationships", DEFAULT_WEIGHTS["relationships"]),
    }

    # Normalize to sum=1.0
    total = sum(weights.values())
    if total > 0 and abs(total - 1.0) > 0.01:
        log.warning("weights_not_normalized", total=total)
        weights = {k: v / total for k, v in weights.items()}

    return weights


def calculate_overall_score(
    scores: list[CompetencyScore],
    weights: dict[str, float],
) -> tuple[float | None, str | None]:
    """Calculate weighted overall score from competency scores.

    Only includes competencies with score != None and confidence > 0.
    Returns (overall_score, label) or (None, None) if insufficient data.
    """
    weighted_sum = 0.0
    weight_sum = 0.0

    for cs in scores:
        if cs.score is None or cs.confidence <= 0:
            continue
        w = weights.get(cs.name, 0.0)
        # Weight by both config weight and confidence
        effective_weight = w * cs.confidence
        weighted_sum += cs.score * effective_weight
        weight_sum += effective_weight

    if weight_sum == 0:
        log.info("no_scorable_competencies")
        return None, None

    overall = weighted_sum / weight_sum
    label = _score_to_label(overall)

    log.info(
        "overall_score_calculated",
        overall=round(overall, 2),
        label=label,
        competencies_scored=sum(1 for s in scores if s.score is not None),
    )
    return round(overall, 2), label


def _score_to_label(score: float) -> str:
    """Map numeric score to performance label."""
    if score >= 4.5:
        return LABEL_EXCEPTIONAL
    elif score >= 3.5:
        return LABEL_EXCEEDS
    elif score >= 2.5:
        return LABEL_MEETS
    elif score >= 1.5:
        return LABEL_DEVELOPING
    else:
        return LABEL_BELOW
