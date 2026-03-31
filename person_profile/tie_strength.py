"""Tie-strength calculation engine.

Computes 6-dimensional relationship strength scores:
  dim_frequency     — normalized log(count) of interactions in 90d window
  dim_recency       — exponential decay from last contact
  dim_reciprocity   — min(sent,received)/max(sent,received)
  dim_channel_div   — active channels / MAX_CHANNELS_NORM
  dim_sentiment     — average NLP sentiment (-1..+1), 0 if unknown
  dim_common_contacts — Jaccard similarity of neighbor sets

Final tie_strength is a weighted sum mapped to [-1, +1].
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from . import config as cfg

log = structlog.get_logger("person_profile.tie_strength")


@dataclass
class DimensionScores:
    frequency: float = 0.0
    recency: float = 0.0
    reciprocity: float = 0.0
    channel_div: float = 0.0
    sentiment: float = 0.0
    common_contacts: float = 0.0

    interaction_count: int = 0
    initiated_by_from: int = 0
    initiated_by_to: int = 0
    dominant_channel: str | None = None


def calculate_dim_frequency(count: int, max_count: int) -> float:
    """Normalize log(count+1) / log(max_count+1)."""
    if max_count <= 0:
        return 0.0
    return math.log(count + 1) / math.log(max_count + 1)


def calculate_dim_recency(days_since_last: int | None) -> float:
    """Exponential decay: exp(-lambda * days)."""
    if days_since_last is None:
        return 0.0
    return math.exp(-cfg.DECAY_LAMBDA * max(days_since_last, 0))


def calculate_dim_reciprocity(sent: int, received: int) -> float:
    """min(sent,received) / max(sent,received)."""
    if sent == 0 and received == 0:
        return 0.0
    return min(sent, received) / max(sent, received)


def calculate_dim_channel_div(active_channels: int) -> float:
    """min(channels, MAX) / MAX."""
    return min(active_channels, cfg.MAX_CHANNELS_NORM) / cfg.MAX_CHANNELS_NORM


def calculate_dim_common_contacts(
    neighbors_a: set[UUID], neighbors_b: set[UUID]
) -> float:
    """Jaccard similarity: |A∩B| / |A∪B|."""
    if not neighbors_a and not neighbors_b:
        return 0.0
    intersection = neighbors_a & neighbors_b
    union = neighbors_a | neighbors_b
    return len(intersection) / len(union) if union else 0.0


def calculate_tie_strength(dims: DimensionScores) -> float:
    """Compute final tie_strength from 6 dimensions.

    Returns a value in [-1.0, +1.0].
    If fewer than MIN_INTERACTIONS_FOR_SCORE interactions, returns DEFAULT_WEAK_SCORE.
    """
    if dims.interaction_count < cfg.MIN_INTERACTIONS_FOR_SCORE:
        return cfg.DEFAULT_WEAK_SCORE

    has_sentiment = dims.sentiment != 0.0

    # Redistribute sentiment weight if no NLP data
    if has_sentiment:
        w_freq = cfg.W_FREQUENCY
        w_rec = cfg.W_RECENCY
        w_recip = cfg.W_RECIPROCITY
        w_chan = cfg.W_CHANNEL_DIV
        w_sent = cfg.W_SENTIMENT
    else:
        # Redistribute 0.20 proportionally among the other 4
        total_other = cfg.W_FREQUENCY + cfg.W_RECENCY + cfg.W_RECIPROCITY + cfg.W_CHANNEL_DIV
        w_freq = cfg.W_FREQUENCY / total_other
        w_rec = cfg.W_RECENCY / total_other
        w_recip = cfg.W_RECIPROCITY / total_other
        w_chan = cfg.W_CHANNEL_DIV / total_other
        w_sent = 0.0

    weighted_sum = (
        w_freq * dims.frequency
        + w_rec * dims.recency
        + w_recip * dims.reciprocity
        + w_chan * dims.channel_div
        + w_sent * max(0, (dims.sentiment + 1) / 2)  # map [-1,1] → [0,1]
    )

    # Scale to [-1, +1]
    score = weighted_sum * 2 - 1

    # Sentiment can pull negative
    if has_sentiment:
        score += dims.sentiment * 0.2

    # Clip
    if not has_sentiment or dims.sentiment >= 0:
        # No negative data → don't create false negatives
        score = max(0.0, min(1.0, score))
    else:
        score = max(-1.0, min(1.0, score))

    return round(score, 4)


# ─── Database-level batch computation ─────────────────────────────────

def _get_max_interaction_count(conn: psycopg.Connection, window_days: int) -> int:
    """Get the maximum interaction count in the DB for normalization."""
    row = conn.execute(
        """SELECT COALESCE(MAX(interaction_count), 1)
           FROM person_relationships
           WHERE last_contact_at > now() - make_interval(days => %s)""",
        (window_days,),
    ).fetchone()
    return row[0]


def _get_neighbors(conn: psycopg.Connection, person_id: UUID, min_strength: float = 0.1) -> set[UUID]:
    """Get set of neighbor person_ids for Jaccard computation."""
    rows = conn.execute(
        """SELECT person_id_to FROM person_relationships
           WHERE person_id_from = %s AND tie_strength >= %s
           UNION
           SELECT person_id_from FROM person_relationships
           WHERE person_id_to = %s AND tie_strength >= %s""",
        (str(person_id), min_strength, str(person_id), min_strength),
    ).fetchall()
    return {r[0] for r in rows}


def compute_pair(
    conn: psycopg.Connection,
    from_id: UUID,
    to_id: UUID,
    max_count: int | None = None,
) -> DimensionScores:
    """Compute all 6 dimensions for a single directed pair."""
    conn.row_factory = dict_row

    if max_count is None:
        max_count = _get_max_interaction_count(conn, cfg.WINDOW_LONG)

    # Get current relationship stats
    rel = conn.execute(
        """SELECT interaction_count, initiated_by_from, initiated_by_to,
                  dominant_channel,
                  EXTRACT(EPOCH FROM (now() - last_contact_at)) / 86400 AS days_since
           FROM person_relationships
           WHERE person_id_from = %s AND person_id_to = %s""",
        (str(from_id), str(to_id)),
    ).fetchone()

    if not rel:
        return DimensionScores()

    # Count distinct channels
    channel_count = conn.execute(
        """SELECT COUNT(DISTINCT channel) FROM person_identities
           WHERE person_id = %s AND is_active = true""",
        (str(to_id),),
    ).fetchone()[0]

    # Average sentiment (from psychographic if available, else 0)
    sent_row = conn.execute(
        "SELECT avg_sentiment FROM person_psychographic WHERE person_id = %s",
        (str(to_id),),
    ).fetchone()
    avg_sentiment = sent_row["avg_sentiment"] if sent_row and sent_row["avg_sentiment"] is not None else 0.0

    # Jaccard
    neighbors_a = _get_neighbors(conn, from_id)
    neighbors_b = _get_neighbors(conn, to_id)

    days_since = int(rel["days_since"]) if rel["days_since"] is not None else None

    dims = DimensionScores(
        frequency=calculate_dim_frequency(rel["interaction_count"], max_count),
        recency=calculate_dim_recency(days_since),
        reciprocity=calculate_dim_reciprocity(
            rel["initiated_by_from"], rel["initiated_by_to"]
        ),
        channel_div=calculate_dim_channel_div(channel_count),
        sentiment=avg_sentiment,
        common_contacts=calculate_dim_common_contacts(neighbors_a, neighbors_b),
        interaction_count=rel["interaction_count"],
        initiated_by_from=rel["initiated_by_from"],
        initiated_by_to=rel["initiated_by_to"],
        dominant_channel=rel["dominant_channel"],
    )
    return dims


def recompute_active_pairs(
    conn: psycopg.Connection,
    since: str | None = None,
) -> int:
    """Recompute tie_strength for all pairs with activity since watermark.

    Also recomputes dim_recency for ALL pairs (decay happens even without activity).
    Returns count of updated pairs.
    """
    max_count = _get_max_interaction_count(conn, cfg.WINDOW_LONG)
    updated = 0

    # Get pairs with recent activity
    if since:
        rows = conn.execute(
            """SELECT person_id_from, person_id_to, is_manual_override
               FROM person_relationships
               WHERE last_contact_at >= %s""",
            (since,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT person_id_from, person_id_to, is_manual_override FROM person_relationships"
        ).fetchall()

    for row in rows:
        pid_from, pid_to, is_manual = row[0], row[1], row[2]
        if is_manual:
            continue

        dims = compute_pair(conn, pid_from, pid_to, max_count)
        score = calculate_tie_strength(dims)

        conn.execute(
            """UPDATE person_relationships SET
                   tie_strength = %s,
                   dim_frequency = %s, dim_recency = %s,
                   dim_reciprocity = %s, dim_channel_div = %s,
                   dim_sentiment = %s, dim_common_contacts = %s,
                   computed_at = now()
               WHERE person_id_from = %s AND person_id_to = %s
                 AND is_manual_override = false""",
            (
                score, dims.frequency, dims.recency, dims.reciprocity,
                dims.channel_div, dims.sentiment, dims.common_contacts,
                str(pid_from), str(pid_to),
            ),
        )
        updated += 1

    # Recompute recency decay for ALL non-active pairs
    conn.execute(
        """UPDATE person_relationships SET
               dim_recency = EXP(-%s * EXTRACT(EPOCH FROM (now() - last_contact_at)) / 86400),
               computed_at = now()
           WHERE is_manual_override = false
             AND last_contact_at IS NOT NULL"""
        + (" AND last_contact_at < %s" if since else ""),
        (cfg.DECAY_LAMBDA,) + ((since,) if since else ()),
    )

    log.info("tie_strength_recomputed", active_pairs=updated)
    return updated
