"""P5: Trajectory perspective — tie strength evolution, lifecycle stage, turning points."""

from __future__ import annotations

from typing import Any

from ..models import PairData


def _safe_get(d: dict | None, key: str, default=None):
    if d is None:
        return default
    return d.get(key, default)


def _determine_lifecycle_stage(
    tie_strength: float | None,
    delta_90d: float | None,
    days_since_last_contact: int | None,
    relationship_duration_days: int | None,
) -> str:
    """Determine lifecycle stage based on tie strength and trajectory.

    Stages:
      new          — relationship < 30 days old
      acquaintance — ts < 0.15
      developing   — ts < 0.35
      established  — ts < 0.55 and d90 >= 0
      close        — ts >= 0.55
      fading       — d90 < -0.15
      dormant      — days_since_last > 180
    """
    if days_since_last_contact is not None and days_since_last_contact > 180:
        return "dormant"

    if relationship_duration_days is not None and relationship_duration_days < 30:
        return "new"

    if delta_90d is not None and delta_90d < -0.15:
        return "fading"

    if tie_strength is None:
        return "unknown"

    ts = float(tie_strength)
    d90 = float(delta_90d) if delta_90d is not None else 0.0

    if ts >= 0.55:
        return "close"
    if ts >= 0.35 and d90 >= 0:
        return "established"
    if ts >= 0.15:
        return "developing"
    return "acquaintance"


def compute_p5(pair_data: PairData, perspective: str) -> dict[str, Any]:
    """Compute trajectory metrics for a given perspective."""
    if perspective == "a_to_b":
        rel = pair_data.rel_a_to_b
        traj = pair_data.trajectory_a_to_b
    else:
        rel = pair_data.rel_b_to_a
        traj = pair_data.trajectory_b_to_a

    trajectory_status = _safe_get(traj, "trajectory_status", "unknown")
    tie_strength_current = _safe_get(traj, "current_tie_strength")
    if tie_strength_current is None:
        tie_strength_current = _safe_get(rel, "tie_strength")

    delta_30d = _safe_get(traj, "delta_30d")
    delta_90d = _safe_get(traj, "delta_90d")
    peak_ts = _safe_get(traj, "peak_tie_strength")
    peak_at = _safe_get(traj, "peak_at")
    days_since = _safe_get(traj, "days_since_last_contact")

    # Relationship duration from first_contact
    first_contact_at = _safe_get(rel, "first_contact_at")
    relationship_duration_days = None
    if first_contact_at is not None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if hasattr(first_contact_at, "tzinfo"):
            relationship_duration_days = max(1, (now - first_contact_at).days)

    lifecycle_stage = _determine_lifecycle_stage(
        tie_strength_current, delta_90d, days_since, relationship_duration_days
    )

    # Turning points: from history_snapshots if available
    turning_points = None
    snapshots = _safe_get(traj, "history_snapshots")
    if snapshots and isinstance(snapshots, list) and len(snapshots) >= 2:
        tp_list = []
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]
            prev_ts = prev.get("tie_strength", 0)
            curr_ts = curr.get("tie_strength", 0)
            delta = curr_ts - prev_ts
            if abs(delta) >= 0.1:
                tp_list.append({
                    "date": curr.get("date"),
                    "from_strength": round(prev_ts, 3),
                    "to_strength": round(curr_ts, 3),
                    "delta": round(delta, 3),
                    "direction": "up" if delta > 0 else "down",
                })
        if tp_list:
            turning_points = tp_list[-5:]  # Keep last 5

    return {
        "trajectory_status": trajectory_status,
        "tie_strength_current": float(tie_strength_current) if tie_strength_current is not None else None,
        "tie_strength_delta_30d": float(delta_30d) if delta_30d is not None else None,
        "tie_strength_delta_90d": float(delta_90d) if delta_90d is not None else None,
        "peak_tie_strength": float(peak_ts) if peak_ts is not None else None,
        "peak_tie_strength_at": peak_at,
        "lifecycle_stage": lifecycle_stage,
        "turning_points": turning_points,
    }
