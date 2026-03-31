"""P2: Asymmetry perspective — initiation balance, response rates, lag, formality."""

from __future__ import annotations

from typing import Any

from ..models import PairData


def _safe_get(d: dict | None, key: str, default=None):
    if d is None:
        return default
    return d.get(key, default)


def compute_p2(pair_data: PairData, perspective: str) -> dict[str, Any]:
    """Compute asymmetry metrics.

    perspective: 'a_to_b' or 'b_to_a'
    """
    if perspective == "a_to_b":
        rel = pair_data.rel_a_to_b
        comm_ego = pair_data.comm_a
        comm_alter = pair_data.comm_b
    else:
        rel = pair_data.rel_b_to_a
        comm_ego = pair_data.comm_b
        comm_alter = pair_data.comm_a

    # Initiation ratio: initiated_by_from / total
    initiated_by_from = _safe_get(rel, "initiated_by_from", 0)
    initiated_by_to = _safe_get(rel, "initiated_by_to", 0)
    total_initiated = initiated_by_from + initiated_by_to

    initiation_ratio = None
    if total_initiated > 0:
        initiation_ratio = round(initiated_by_from / total_initiated, 3)

    # Response rate: dim_reciprocity is a proxy for mutual responsiveness
    response_rate = _safe_get(rel, "dim_reciprocity")

    # Lag: use avg_response_time_min from communication patterns
    avg_lag_ego = _safe_get(comm_ego, "avg_response_time_min")
    avg_lag_alter = _safe_get(comm_alter, "avg_response_time_min")

    avg_lag_ego_minutes = float(avg_lag_ego) if avg_lag_ego is not None else None
    avg_lag_alter_minutes = float(avg_lag_alter) if avg_lag_alter is not None else None

    # Lag asymmetry: (ego_lag - alter_lag) / max(ego, alter) in [-1, 1]
    # Positive = ego responds slower; negative = ego responds faster
    lag_asymmetry = None
    if avg_lag_ego_minutes is not None and avg_lag_alter_minutes is not None:
        max_lag = max(avg_lag_ego_minutes, avg_lag_alter_minutes)
        if max_lag > 0:
            lag_asymmetry = round(
                (avg_lag_ego_minutes - avg_lag_alter_minutes) / max_lag, 3
            )
        else:
            lag_asymmetry = 0.0

    # Formality
    formality_ego = _safe_get(comm_ego, "formality_score")
    formality_alter = _safe_get(comm_alter, "formality_score")

    formality_score_ego = float(formality_ego) if formality_ego is not None else None
    formality_score_alter = float(formality_alter) if formality_alter is not None else None

    formality_asymmetry = None
    if formality_score_ego is not None and formality_score_alter is not None:
        formality_asymmetry = round(formality_score_ego - formality_score_alter, 3)

    return {
        "initiation_ratio": initiation_ratio,
        "response_rate": response_rate,
        "avg_lag_ego_minutes": avg_lag_ego_minutes,
        "avg_lag_alter_minutes": avg_lag_alter_minutes,
        "lag_asymmetry": lag_asymmetry,
        "formality_score_ego": formality_score_ego,
        "formality_score_alter": formality_score_alter,
        "formality_asymmetry": formality_asymmetry,
    }
