"""ROI Synergy Calculator — bonus when an insight benefits multiple entities."""
from __future__ import annotations

import structlog
from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

# Synergy multiplier: each additional entity sharing the same activity type
# in a period adds this fraction of the original value
SYNERGY_MULTIPLIER = 0.15


def calculate_synergy(period_start: str, period_end: str) -> dict:
    """
    Find activities that benefited multiple entities in a period
    and compute synergy bonuses.

    Returns: {"synergies_found": int, "total_bonus_pln": float, "details": [...]}
    """
    details = []
    total_bonus = 0.0

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Find activity types used by multiple entities in the period
            cur.execute(
                """
                SELECT activity_type, COUNT(DISTINCT entity_id) as entity_count,
                       SUM(value_pln) as total_value
                FROM roi_activities
                WHERE created_at >= %s AND created_at < %s
                GROUP BY activity_type
                HAVING COUNT(DISTINCT entity_id) > 1
                """,
                (period_start, period_end),
            )
            shared = cur.fetchall()

            for activity_type, entity_count, total_value in shared:
                bonus = round(float(total_value) * SYNERGY_MULTIPLIER * (entity_count - 1), 2)
                total_bonus += bonus
                details.append({
                    "activity_type": activity_type,
                    "entities_sharing": entity_count,
                    "base_value_pln": float(total_value),
                    "synergy_bonus_pln": bonus,
                })

            # Also check: same source content used by different domains
            cur.execute(
                """
                SELECT source_table, source_id, COUNT(DISTINCT domain) as domain_count,
                       SUM(value_pln) as total_value
                FROM roi_activities
                WHERE created_at >= %s AND created_at < %s
                  AND source_table IS NOT NULL AND source_id IS NOT NULL
                GROUP BY source_table, source_id
                HAVING COUNT(DISTINCT domain) > 1
                """,
                (period_start, period_end),
            )
            cross_domain = cur.fetchall()

            for source_table, source_id, domain_count, total_value in cross_domain:
                bonus = round(float(total_value) * SYNERGY_MULTIPLIER * (domain_count - 1), 2)
                total_bonus += bonus
                details.append({
                    "type": "cross_domain",
                    "source": f"{source_table}:{source_id}",
                    "domains_sharing": domain_count,
                    "synergy_bonus_pln": bonus,
                })

    log.info("roi_synergy_calculated", synergies=len(details), total_bonus=total_bonus)
    return {
        "synergies_found": len(details),
        "total_bonus_pln": round(total_bonus, 2),
        "details": details,
    }
