"""Collects all data needed for relationship analysis from person_profile tables."""

from __future__ import annotations

from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from .models import PairData

log = structlog.get_logger("relationship_analyzer.data_collector")


def _fetch_one(conn: psycopg.Connection, query: str, params: tuple) -> dict | None:
    """Fetch a single row as dict, or None."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchone()


def _fetch_all(conn: psycopg.Connection, query: str, params: tuple) -> list[dict]:
    """Fetch all rows as list of dicts."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def collect_pair_data(
    person_id_a: UUID,
    person_id_b: UUID,
    conn: psycopg.Connection,
    data_window_days: int = 365,
) -> PairData:
    """Pull all relevant data for a pair from person_profile tables.

    Uses parameterized queries exclusively. Returns PairData with whatever
    data is available (missing tables yield None).
    """
    a = str(person_id_a)
    b = str(person_id_b)

    # Display names
    name_a_row = _fetch_one(conn, "SELECT display_name FROM persons WHERE person_id = %s", (a,))
    name_b_row = _fetch_one(conn, "SELECT display_name FROM persons WHERE person_id = %s", (b,))
    name_a = name_a_row["display_name"] if name_a_row else ""
    name_b = name_b_row["display_name"] if name_b_row else ""

    # person_relationships (directed)
    rel_a_to_b = _fetch_one(
        conn,
        "SELECT * FROM person_relationships WHERE person_id_from = %s AND person_id_to = %s",
        (a, b),
    )
    rel_b_to_a = _fetch_one(
        conn,
        "SELECT * FROM person_relationships WHERE person_id_from = %s AND person_id_to = %s",
        (b, a),
    )

    # person_behavioral
    behavioral_a = _fetch_one(conn, "SELECT * FROM person_behavioral WHERE person_id = %s", (a,))
    behavioral_b = _fetch_one(conn, "SELECT * FROM person_behavioral WHERE person_id = %s", (b,))

    # person_communication_pattern
    comm_a = _fetch_one(conn, "SELECT * FROM person_communication_pattern WHERE person_id = %s", (a,))
    comm_b = _fetch_one(conn, "SELECT * FROM person_communication_pattern WHERE person_id = %s", (b,))

    # person_psychographic
    psycho_a = _fetch_one(conn, "SELECT * FROM person_psychographic WHERE person_id = %s", (a,))
    psycho_b = _fetch_one(conn, "SELECT * FROM person_psychographic WHERE person_id = %s", (b,))

    # person_open_loops
    open_loops_a = _fetch_all(
        conn,
        "SELECT * FROM person_open_loops WHERE person_id = %s AND status = 'open'",
        (a,),
    )
    open_loops_b = _fetch_all(
        conn,
        "SELECT * FROM person_open_loops WHERE person_id = %s AND status = 'open'",
        (b,),
    )

    # person_shared_context
    shared_context_a = _fetch_all(
        conn,
        "SELECT * FROM person_shared_context WHERE person_id = %s ORDER BY mention_count DESC LIMIT 50",
        (a,),
    )
    shared_context_b = _fetch_all(
        conn,
        "SELECT * FROM person_shared_context WHERE person_id = %s ORDER BY mention_count DESC LIMIT 50",
        (b,),
    )

    # person_relationship_trajectory
    trajectory_a_to_b = _fetch_one(
        conn,
        "SELECT * FROM person_relationship_trajectory WHERE person_id = %s AND person_id_to = %s",
        (a, b),
    )
    trajectory_b_to_a = _fetch_one(
        conn,
        "SELECT * FROM person_relationship_trajectory WHERE person_id = %s AND person_id_to = %s",
        (b, a),
    )

    # person_origin
    origin_a = _fetch_one(conn, "SELECT * FROM person_origin WHERE person_id = %s", (a,))
    origin_b = _fetch_one(conn, "SELECT * FROM person_origin WHERE person_id = %s", (b,))

    # person_professional
    professional_a = _fetch_one(conn, "SELECT * FROM person_professional WHERE person_id = %s", (a,))
    professional_b = _fetch_one(conn, "SELECT * FROM person_professional WHERE person_id = %s", (b,))

    # Shared contacts: persons connected to both A and B
    shared_contacts_row = _fetch_one(
        conn,
        """SELECT COUNT(DISTINCT shared_id) AS cnt FROM (
            SELECT person_id_to AS shared_id FROM person_relationships
            WHERE person_id_from = %s AND tie_strength >= 0.1
            INTERSECT
            SELECT person_id_to AS shared_id FROM person_relationships
            WHERE person_id_from = %s AND tie_strength >= 0.1
        ) sub""",
        (a, b),
    )
    shared_contacts_count = shared_contacts_row["cnt"] if shared_contacts_row else 0

    pair = PairData(
        person_id_a=person_id_a,
        person_id_b=person_id_b,
        data_window_days=data_window_days,
        rel_a_to_b=rel_a_to_b,
        rel_b_to_a=rel_b_to_a,
        behavioral_a=behavioral_a,
        behavioral_b=behavioral_b,
        comm_a=comm_a,
        comm_b=comm_b,
        psycho_a=psycho_a,
        psycho_b=psycho_b,
        open_loops_a=open_loops_a,
        open_loops_b=open_loops_b,
        shared_context_a=shared_context_a,
        shared_context_b=shared_context_b,
        trajectory_a_to_b=trajectory_a_to_b,
        trajectory_b_to_a=trajectory_b_to_a,
        origin_a=origin_a,
        origin_b=origin_b,
        professional_a=professional_a,
        professional_b=professional_b,
        name_a=name_a,
        name_b=name_b,
        shared_contacts_count=shared_contacts_count,
    )

    log.debug(
        "pair_data_collected",
        person_a=name_a,
        person_b=name_b,
        has_rel_ab=rel_a_to_b is not None,
        has_rel_ba=rel_b_to_a is not None,
    )

    return pair
