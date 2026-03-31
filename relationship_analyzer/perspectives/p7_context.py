"""P7: Context perspective — origin, shared contacts, open loops, shared experiences."""

from __future__ import annotations

from typing import Any

from ..models import PairData


def _safe_get(d: dict | None, key: str, default=None):
    if d is None:
        return default
    return d.get(key, default)


def compute_p7(pair_data: PairData, perspective: str) -> dict[str, Any]:
    """Compute context/history metrics.

    Uses person_origin, person_open_loops, person_shared_context, and
    the shared_contacts_count from data collection.
    """
    if perspective == "a_to_b":
        rel = pair_data.rel_a_to_b
        origin_alter = pair_data.origin_b
        open_loops = pair_data.open_loops_b
        shared_ctx_alter = pair_data.shared_context_b
    else:
        rel = pair_data.rel_b_to_a
        origin_alter = pair_data.origin_a
        open_loops = pair_data.open_loops_a
        shared_ctx_alter = pair_data.shared_context_a

    # First contact
    first_contact_at = _safe_get(rel, "first_contact_at")

    # Origin
    origin_type = _safe_get(origin_alter, "origin_type")
    origin_context = _safe_get(origin_alter, "origin_context")

    # Shared contacts (symmetric, same for both directions)
    shared_contacts_count = pair_data.shared_contacts_count

    # Open loops count
    open_loops_count = len(open_loops)

    # Shared experiences from person_origin
    shared_experiences = _safe_get(origin_alter, "shared_experiences")
    shared_experiences_count = 0
    if shared_experiences and isinstance(shared_experiences, list):
        shared_experiences_count = len(shared_experiences)

    # Milestone count: significant events in shared_context (entity_type = 'milestone', 'event', 'decision')
    milestone_types = {"milestone", "event", "decision", "achievement"}
    milestone_count = sum(
        1 for sc in shared_ctx_alter
        if sc.get("entity_type", "").lower() in milestone_types
    )

    return {
        "first_contact_at": first_contact_at,
        "origin_type": origin_type,
        "origin_context": origin_context,
        "shared_contacts_count": shared_contacts_count,
        "open_loops_count": open_loops_count,
        "shared_experiences_count": shared_experiences_count,
        "milestone_count": milestone_count,
    }
