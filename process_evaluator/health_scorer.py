"""Health scoring: weighted overall score, failure risk, process box."""

from __future__ import annotations

import structlog

from .models import DimensionScore

log = structlog.get_logger("process_evaluator.health_scorer")

# Dimension weights per process_type
_WEIGHTS: dict[str, dict[str, float]] = {
    "engineering": {
        "throughput": 0.20, "quality": 0.25, "maturity": 0.10, "handoff": 0.10,
        "cost": 0.15, "improvement": 0.05, "scalability": 0.10, "dependency": 0.05,
    },
    "sales": {
        "throughput": 0.30, "quality": 0.15, "maturity": 0.10, "handoff": 0.05,
        "cost": 0.20, "improvement": 0.05, "scalability": 0.10, "dependency": 0.05,
    },
    "customer_service": {
        "throughput": 0.15, "quality": 0.35, "maturity": 0.10, "handoff": 0.15,
        "cost": 0.10, "improvement": 0.05, "scalability": 0.05, "dependency": 0.05,
    },
}

# Default: equal weights across all 8 dimensions
_DEFAULT_WEIGHT = 1.0 / 8.0

# Health labels
_HEALTH_LABELS = [
    (75.0, "excellent"),
    (55.0, "good"),
    (35.0, "fair"),
    (15.0, "at_risk"),
    (0.0, "critical"),
]

# Process box boundaries
_BOX_HIGH = 65.0
_BOX_LOW = 40.0
_PML_HIGH = 4
_PML_LOW = 3


def calculate_health_score(
    scores: list[DimensionScore],
    process_type: str,
) -> tuple[float, str]:
    """Calculate overall health score [20-100] and label.

    Args:
        scores: List of 8 dimension scores.
        process_type: Type for weight selection.

    Returns:
        (health_score, health_label)
    """
    weights = _WEIGHTS.get(process_type, {})
    score_map = {s.name: s for s in scores}

    weighted_sum = 0.0
    total_weight = 0.0

    for dim_name in ("throughput", "quality", "maturity", "handoff",
                     "cost", "improvement", "scalability", "dependency"):
        ds = score_map.get(dim_name)
        w = weights.get(dim_name, _DEFAULT_WEIGHT)

        if ds and ds.score is not None:
            weighted_sum += ds.score * w
            total_weight += w

    if total_weight == 0:
        return 20.0, "critical"

    weighted_avg = weighted_sum / total_weight
    # Scale from [1,5] to [20,100]
    health_score = round(weighted_avg * 20.0, 1)
    health_score = max(20.0, min(100.0, health_score))

    label = "critical"
    for threshold, lbl in _HEALTH_LABELS:
        if health_score >= threshold:
            label = lbl
            break

    log.debug(
        "health_score_calculated",
        health_score=health_score,
        label=label,
        process_type=process_type,
    )

    return health_score, label


def calculate_failure_risk(scores_dict: dict[str, DimensionScore]) -> float:
    """Calculate failure risk [0-1].

    Formula:
        0.40 * (1 - D8/5)  — dependency risk dominates
      + 0.30 * max(0, (3-D1)/3) — throughput deficit
      + 0.20 * (1 - D2/5)  — quality deficit
      + 0.10 * (1 - D3/5)  — maturity deficit
    """
    d8 = scores_dict.get("dependency")
    d1 = scores_dict.get("throughput")
    d2 = scores_dict.get("quality")
    d3 = scores_dict.get("maturity")

    d8_val = d8.score if d8 and d8.score is not None else 3.0
    d1_val = d1.score if d1 and d1.score is not None else 3.0
    d2_val = d2.score if d2 and d2.score is not None else 3.0
    d3_val = d3.score if d3 and d3.score is not None else 3.0

    risk = (
        0.40 * (1.0 - d8_val / 5.0)
        + 0.30 * max(0.0, (3.0 - d1_val) / 3.0)
        + 0.20 * (1.0 - d2_val / 5.0)
        + 0.10 * (1.0 - d3_val / 5.0)
    )

    return round(max(0.0, min(1.0, risk)), 3)


def calculate_process_box(
    health_score: float,
    maturity_level: int | None,
) -> tuple[str, str, str]:
    """Calculate process box position (Health x Maturity).

    Returns:
        (health_axis, maturity_axis, box_label)
    """
    # Health axis
    if health_score > _BOX_HIGH:
        health_axis = "high"
    elif health_score >= _BOX_LOW:
        health_axis = "medium"
    else:
        health_axis = "low"

    # Maturity axis
    pml = maturity_level or 2
    if pml >= _PML_HIGH:
        maturity_axis = "high"
    elif pml >= _PML_LOW:
        maturity_axis = "medium"
    else:
        maturity_axis = "low"

    # Label mapping
    _LABELS = {
        ("high", "high"): "Institutionalized",
        ("high", "medium"): "Well-Run",
        ("high", "low"): "Hero-Dependent",
        ("medium", "high"): "Mature but Strained",
        ("medium", "medium"): "Developing",
        ("medium", "low"): "Ad-Hoc Functional",
        ("low", "high"): "Broken Process",
        ("low", "medium"): "Struggling",
        ("low", "low"): "Wild West",
    }

    label = _LABELS.get((health_axis, maturity_axis), "Developing")

    log.debug(
        "process_box_calculated",
        health_axis=health_axis,
        maturity_axis=maturity_axis,
        label=label,
    )

    return health_axis, maturity_axis, label
