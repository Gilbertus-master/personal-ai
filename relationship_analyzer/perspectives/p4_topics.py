"""P4: Topics perspective — shared topics, topic evolution, discussion depth."""

from __future__ import annotations

from typing import Any

from ..models import PairData


def _safe_get(d: dict | None, key: str, default=None):
    if d is None:
        return default
    return d.get(key, default)


def compute_p4(pair_data: PairData, perspective: str) -> dict[str, Any]:
    """Compute topic/content metrics.

    Uses person_shared_context for top_topics and shared entities.
    Discussion depth is proxied from avg_message_length in communication patterns.
    """
    if perspective == "a_to_b":
        shared_ctx_ego = pair_data.shared_context_a
        shared_ctx_alter = pair_data.shared_context_b
        comm_ego = pair_data.comm_a
    else:
        shared_ctx_ego = pair_data.shared_context_b
        shared_ctx_alter = pair_data.shared_context_a
        comm_ego = pair_data.comm_b

    # Top topics: entity_type='topic' entries from shared_context, sorted by mention_count
    ego_topics = [
        sc["entity_value"]
        for sc in shared_ctx_ego
        if sc.get("entity_type") in ("topic", "project", "company", "deal")
    ]
    alter_topics = [
        sc["entity_value"]
        for sc in shared_ctx_alter
        if sc.get("entity_type") in ("topic", "project", "company", "deal")
    ]

    # Merge and deduplicate, keeping order (ego first)
    seen = set()
    top_topics = []
    for t in ego_topics + alter_topics:
        tl = t.lower().strip()
        if tl not in seen:
            seen.add(tl)
            top_topics.append(t)
    top_topics = top_topics[:15]  # Limit

    # Topics evolution: group by entity_type to see breadth
    topic_type_counts: dict[str, int] = {}
    for sc in shared_ctx_ego:
        et = sc.get("entity_type", "unknown")
        topic_type_counts[et] = topic_type_counts.get(et, 0) + sc.get("mention_count", 1)
    topics_evolution = {"ego_entity_type_counts": topic_type_counts} if topic_type_counts else None

    # Shared entities: entities that appear in both A and B contexts
    ego_entities = {(sc.get("entity_type", ""), sc.get("entity_value", "").lower()) for sc in shared_ctx_ego}
    alter_entities = {(sc.get("entity_type", ""), sc.get("entity_value", "").lower()) for sc in shared_ctx_alter}
    shared_entities_count = len(ego_entities & alter_entities)

    # Discussion depth: proxy from avg_message_length
    # Normalize: <50 chars = shallow (0.2), 50-150 = medium (0.5), 150-300 = deep (0.75), 300+ = very deep (1.0)
    avg_msg_len = _safe_get(comm_ego, "avg_message_length")
    discussion_depth_score = None
    if avg_msg_len is not None:
        avg_msg_len = int(avg_msg_len)
        if avg_msg_len < 50:
            discussion_depth_score = 0.2
        elif avg_msg_len < 150:
            discussion_depth_score = 0.5
        elif avg_msg_len < 300:
            discussion_depth_score = 0.75
        else:
            discussion_depth_score = 1.0

    return {
        "top_topics": top_topics if top_topics else None,
        "topics_evolution": topics_evolution,
        "shared_entities_count": shared_entities_count,
        "discussion_depth_score": discussion_depth_score,
    }
