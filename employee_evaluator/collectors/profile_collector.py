"""Collect evaluation-relevant data from existing person_profile tables.

Primary data source: person_profile tables contain rich behavioral,
communication, network, and relationship data.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

log = structlog.get_logger("employee_evaluator.profile_collector")


def collect_profile_data(person_id: UUID, conn: psycopg.Connection) -> dict[str, Any]:
    """Collect all evaluation-relevant data from person_profile tables.

    Returns a dict with keys: person, professional, behavioral,
    communication, network, open_loops, relationships, trajectory.
    """
    result: dict[str, Any] = {}

    result["person"] = _collect_person(person_id, conn)
    result["professional"] = _collect_professional(person_id, conn)
    result["behavioral"] = _collect_behavioral(person_id, conn)
    result["communication"] = _collect_communication_pattern(person_id, conn)
    result["network"] = _collect_network_position(person_id, conn)
    result["open_loops"] = _collect_open_loops(person_id, conn)
    result["relationships"] = _collect_relationships(person_id, conn)
    result["trajectory"] = _collect_trajectory(person_id, conn)

    log.info(
        "profile_data_collected",
        person_id=str(person_id),
        sections_with_data=sum(1 for v in result.values() if v),
    )
    return result


def _collect_person(person_id: UUID, conn: psycopg.Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT person_id, display_name, tags, notes
               FROM persons WHERE person_id = %s""",
            (str(person_id),),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _collect_professional(person_id: UUID, conn: psycopg.Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT company, job_title, department, seniority,
                      skills, years_in_role, employment_type,
                      reports_to, direct_reports_count
               FROM person_professional
               WHERE person_id = %s
               ORDER BY updated_at DESC NULLS LAST
               LIMIT 1""",
            (str(person_id),),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _collect_behavioral(person_id: UUID, conn: psycopg.Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT communication_style, decision_style, conflict_style,
                      work_style, stress_indicators, motivators,
                      personality_traits, confidence, source
               FROM person_behavioral
               WHERE person_id = %s
               ORDER BY updated_at DESC NULLS LAST
               LIMIT 1""",
            (str(person_id),),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _collect_communication_pattern(
    person_id: UUID, conn: psycopg.Connection
) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT preferred_channels, avg_response_time_hours,
                      response_consistency, active_hours,
                      message_length_avg, formality_level,
                      emoji_frequency, topics_discussed,
                      communication_frequency_weekly,
                      last_inbound_at, last_outbound_at
               FROM person_communication_pattern
               WHERE person_id = %s
               ORDER BY updated_at DESC NULLS LAST
               LIMIT 1""",
            (str(person_id),),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _collect_network_position(
    person_id: UUID, conn: psycopg.Connection
) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT degree_centrality, betweenness_centrality,
                      influence_score, is_broker, is_bridge,
                      cluster_id, cluster_role,
                      avg_tie_strength, strongest_ties, weakest_ties
               FROM person_network_position
               WHERE person_id = %s
               ORDER BY computed_at DESC NULLS LAST
               LIMIT 1""",
            (str(person_id),),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _collect_open_loops(
    person_id: UUID, conn: psycopg.Connection
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT loop_type, status, priority, summary,
                      created_at, due_date, resolved_at
               FROM person_open_loops
               WHERE person_id = %s
                 AND status IN ('open', 'stale')
               ORDER BY priority DESC, created_at DESC
               LIMIT 50""",
            (str(person_id),),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def _collect_relationships(
    person_id: UUID, conn: psycopg.Connection
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT pr.person_id_b, p.display_name AS other_name,
                      pr.relationship_type, pr.tie_strength,
                      pr.sentiment_avg, pr.interaction_count,
                      pr.last_interaction_at, pr.status
               FROM person_relationships pr
               JOIN persons p ON p.person_id = pr.person_id_b
               WHERE pr.person_id_a = %s
               ORDER BY pr.tie_strength DESC NULLS LAST
               LIMIT 30""",
            (str(person_id),),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def _collect_trajectory(
    person_id: UUID, conn: psycopg.Connection
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT person_id_b, direction, velocity,
                      current_phase, risk_level, insight,
                      computed_at
               FROM person_relationship_trajectory
               WHERE person_id_a = %s
               ORDER BY computed_at DESC
               LIMIT 20""",
            (str(person_id),),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]
