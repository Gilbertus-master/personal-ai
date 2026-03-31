"""Enrich evaluation with relationship analysis data."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

log = structlog.get_logger("employee_evaluator.relationship_enricher")


def enrich_with_relationships(
    person_id: UUID, conn: psycopg.Connection
) -> dict[str, Any]:
    """Pull relationship data from relationship_analyses and person_network_position.

    Returns dict with: avg_health, growing_count, cooling_count,
    total_relationships, top_relationships, bottom_relationships.
    """
    result: dict[str, Any] = {
        "avg_health": 0.0,
        "growing_count": 0,
        "cooling_count": 0,
        "stable_count": 0,
        "total_relationships": 0,
        "top_relationships": [],
        "bottom_relationships": [],
    }

    # ── Relationship analyses ────────────────────────────────────────
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT ra.person_id_b, p.display_name,
                          ra.overall_health, ra.trajectory_direction,
                          ra.key_strengths, ra.risk_factors,
                          ra.analyzed_at
                   FROM relationship_analyses ra
                   JOIN persons p ON p.person_id = ra.person_id_b
                   WHERE ra.person_id_a = %s
                   ORDER BY ra.analyzed_at DESC""",
                (str(person_id),),
            )
            analyses = cur.fetchall()
    except Exception:
        log.warning("relationship_analyses_table_missing", person_id=str(person_id))
        analyses = []

    if analyses:
        result["total_relationships"] = len(analyses)

        health_values = [
            a["overall_health"] for a in analyses
            if a.get("overall_health") is not None
        ]
        if health_values:
            result["avg_health"] = sum(health_values) / len(health_values)

        for a in analyses:
            direction = a.get("trajectory_direction", "stable")
            if direction == "growing":
                result["growing_count"] += 1
            elif direction in ("cooling", "declining"):
                result["cooling_count"] += 1
            else:
                result["stable_count"] += 1

        # Top 5 by health
        sorted_by_health = sorted(
            analyses,
            key=lambda x: x.get("overall_health") or 0,
            reverse=True,
        )
        result["top_relationships"] = [
            {
                "name": a["display_name"],
                "health": a.get("overall_health"),
                "direction": a.get("trajectory_direction"),
            }
            for a in sorted_by_health[:5]
        ]
        result["bottom_relationships"] = [
            {
                "name": a["display_name"],
                "health": a.get("overall_health"),
                "direction": a.get("trajectory_direction"),
            }
            for a in sorted_by_health[-3:]
            if a.get("overall_health") is not None
        ]

    # ── Network position ─────────────────────────────────────────────
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT influence_score, degree_centrality,
                          betweenness_centrality, is_broker,
                          avg_tie_strength
                   FROM person_network_position
                   WHERE person_id = %s
                   ORDER BY computed_at DESC NULLS LAST
                   LIMIT 1""",
                (str(person_id),),
            )
            network = cur.fetchone()
    except Exception:
        log.warning("network_position_missing", person_id=str(person_id))
        network = None

    if network:
        result["influence_score"] = network.get("influence_score")
        result["degree_centrality"] = network.get("degree_centrality")
        result["betweenness_centrality"] = network.get("betweenness_centrality")
        result["is_broker"] = network.get("is_broker", False)
        result["network_avg_tie"] = network.get("avg_tie_strength")

    log.info(
        "relationships_enriched",
        person_id=str(person_id),
        total=result["total_relationships"],
        avg_health=round(result["avg_health"], 3),
    )
    return result
