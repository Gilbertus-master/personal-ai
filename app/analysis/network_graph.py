"""
Communication Network Graph — builds communication graph showing who talks
to whom, how often, and through which channels.

Functions:
- build_weekly_graph(week_start): build graph from chunks mentioning multiple people
- detect_silos(): find groups that don't communicate across
- detect_bottlenecks(): find people appearing in >30% of communication paths
- get_network_summary(): overall stats
- run_network_analysis(): full pipeline
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from itertools import combinations
from typing import Any

import structlog
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

log = structlog.get_logger(__name__)


def _ensure_tables() -> None:
    """Create communication_edges table if it doesn't exist."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS communication_edges (
                    id BIGSERIAL PRIMARY KEY,
                    person_a TEXT NOT NULL,
                    person_b TEXT NOT NULL,
                    channel TEXT,
                    message_count INT DEFAULT 0,
                    last_communication TIMESTAMPTZ,
                    topics TEXT[],
                    week_start DATE NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(person_a, person_b, channel, week_start)
                );

                CREATE INDEX IF NOT EXISTS idx_comm_edges_persons
                    ON communication_edges(person_a, person_b);
                CREATE INDEX IF NOT EXISTS idx_comm_edges_week
                    ON communication_edges(week_start);
            """)
        conn.commit()
    log.debug("communication_edges_table_ensured")


def build_weekly_graph(week_start: str | None = None) -> dict[str, Any]:
    """Build communication graph from chunks mentioning multiple people.

    For each chunk that mentions 2+ person entities, create an edge
    between each pair. Channel = source_type of the document.
    """
    _ensure_tables()

    if week_start is None:
        # Default to current week (Monday)
        today = date.today()
        week_start_date = today - timedelta(days=today.weekday())
        week_start = week_start_date.isoformat()

    week_end = (date.fromisoformat(week_start) + timedelta(days=7)).isoformat()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Find chunks from this week that mention 2+ persons
            cur.execute("""
                SELECT
                    c.id as chunk_id,
                    s.source_type as channel,
                    d.created_at,
                    ARRAY_AGG(DISTINCT COALESCE(en.canonical_name, en.name)) as persons
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = d.source_id
                JOIN chunk_entities ce ON ce.chunk_id = c.id
                JOIN entities en ON en.id = ce.entity_id
                WHERE en.entity_type = 'person'
                  AND d.created_at >= %s::date
                  AND d.created_at < %s::date
                GROUP BY c.id, s.source_type, d.created_at
                HAVING COUNT(DISTINCT en.id) >= 2
                ORDER BY d.created_at DESC
            """, (week_start, week_end))
            rows = cur.fetchall()

    if not rows:
        log.info("no_multi_person_chunks", week_start=week_start)
        return {"week_start": week_start, "edges_created": 0, "chunks_processed": 0}

    # Build edges from co-occurrences
    edge_counts: dict[tuple[str, str, str], dict] = {}
    for chunk_id, channel, created_at, persons in rows:
        # Generate all pairs (sorted to ensure consistency)
        for person_a, person_b in combinations(sorted(persons), 2):
            key = (person_a, person_b, channel or "unknown")
            if key not in edge_counts:
                edge_counts[key] = {
                    "message_count": 0,
                    "last_communication": created_at,
                }
            edge_counts[key]["message_count"] += 1
            if created_at and (
                edge_counts[key]["last_communication"] is None
                or created_at > edge_counts[key]["last_communication"]
            ):
                edge_counts[key]["last_communication"] = created_at

    # Upsert edges
    edges_created = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for (person_a, person_b, channel), data in edge_counts.items():
                cur.execute("""
                    INSERT INTO communication_edges
                        (person_a, person_b, channel, message_count,
                         last_communication, week_start)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (person_a, person_b, channel, week_start)
                    DO UPDATE SET
                        message_count = EXCLUDED.message_count,
                        last_communication = EXCLUDED.last_communication
                    RETURNING id
                """, (
                    person_a, person_b, channel,
                    data["message_count"],
                    data["last_communication"],
                    week_start,
                ))
                if cur.fetchone():
                    edges_created += 1
        conn.commit()

    log.info("weekly_graph_built",
             week_start=week_start, edges=edges_created, chunks=len(rows))
    return {
        "week_start": week_start,
        "edges_created": edges_created,
        "chunks_processed": len(rows),
    }


def detect_silos() -> list[dict[str, Any]]:
    """Find organization pairs that don't communicate across.

    Groups people by organization (from relationships table),
    checks if there are edges between groups.
    """
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Get people grouped by organization
            cur.execute("""
                SELECT
                    p.first_name || ' ' || COALESCE(p.last_name, '') as person_name,
                    r.organization
                FROM people p
                JOIN relationships r ON r.person_id = p.id
                WHERE r.organization IS NOT NULL
                  AND r.status = 'active'
            """)
            person_orgs = cur.fetchall()

    if not person_orgs:
        return []

    # Build org -> people mapping
    org_people: dict[str, set[str]] = {}
    for person_name, org in person_orgs:
        org_people.setdefault(org, set()).add(person_name.strip().lower())

    orgs = list(org_people.keys())
    if len(orgs) < 2:
        return []

    # Check cross-org communication (last 4 weeks)
    silos = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for org_a, org_b in combinations(sorted(orgs), 2):
                people_a = list(org_people[org_a])
                people_b = list(org_people[org_b])

                # Count edges between the two groups
                cur.execute("""
                    SELECT COUNT(*), COALESCE(SUM(message_count), 0)
                    FROM communication_edges
                    WHERE week_start > CURRENT_DATE - INTERVAL '28 days'
                      AND (
                          (LOWER(person_a) = ANY(%s) AND LOWER(person_b) = ANY(%s))
                          OR (LOWER(person_a) = ANY(%s) AND LOWER(person_b) = ANY(%s))
                      )
                """, (people_a, people_b, people_b, people_a))
                row = cur.fetchone()
                edge_count, msg_count = row

                if edge_count < 3:
                    silos.append({
                        "org_a": org_a,
                        "org_b": org_b,
                        "cross_edges": edge_count,
                        "cross_messages": msg_count,
                        "people_in_a": len(org_people[org_a]),
                        "people_in_b": len(org_people[org_b]),
                        "severity": "high" if edge_count == 0 else "medium",
                    })

    return sorted(silos, key=lambda s: s["cross_edges"])


def detect_bottlenecks(threshold: float = 0.30) -> list[dict[str, Any]]:
    """Find people appearing in >threshold fraction of all edges (last 4 weeks)."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Total edges in last 4 weeks
            cur.execute("""
                SELECT COUNT(*)
                FROM communication_edges
                WHERE week_start > CURRENT_DATE - INTERVAL '28 days'
            """)
            total_edges = cur.fetchone()[0]

            if total_edges == 0:
                return []

            # Count edges per person (appearing as either person_a or person_b)
            cur.execute("""
                WITH person_edges AS (
                    SELECT person_a as person_name, COUNT(*) as edge_count
                    FROM communication_edges
                    WHERE week_start > CURRENT_DATE - INTERVAL '28 days'
                    GROUP BY person_a
                    UNION ALL
                    SELECT person_b as person_name, COUNT(*) as edge_count
                    FROM communication_edges
                    WHERE week_start > CURRENT_DATE - INTERVAL '28 days'
                    GROUP BY person_b
                )
                SELECT person_name, SUM(edge_count) as total_edges
                FROM person_edges
                GROUP BY person_name
                ORDER BY total_edges DESC
            """)
            rows = cur.fetchall()

    bottlenecks = []
    for person_name, person_edges in rows:
        ratio = person_edges / total_edges if total_edges > 0 else 0
        if ratio >= threshold:
            bottlenecks.append({
                "person_name": person_name,
                "edge_count": person_edges,
                "total_edges": total_edges,
                "ratio": round(ratio, 3),
                "severity": "critical" if ratio > 0.5 else "high" if ratio > 0.4 else "medium",
            })

    return bottlenecks


def get_network_summary() -> dict[str, Any]:
    """Overall network stats: total edges, most/least connected."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Total edges and unique people (last 4 weeks)
            cur.execute("""
                SELECT
                    COUNT(*) as total_edges,
                    COALESCE(SUM(message_count), 0) as total_messages
                FROM communication_edges
                WHERE week_start > CURRENT_DATE - INTERVAL '28 days'
            """)
            row = cur.fetchone()
            total_edges, total_messages = row

            # Most connected people
            cur.execute("""
                WITH person_edges AS (
                    SELECT person_a as person_name, message_count
                    FROM communication_edges
                    WHERE week_start > CURRENT_DATE - INTERVAL '28 days'
                    UNION ALL
                    SELECT person_b as person_name, message_count
                    FROM communication_edges
                    WHERE week_start > CURRENT_DATE - INTERVAL '28 days'
                )
                SELECT person_name,
                       COUNT(*) as connections,
                       SUM(message_count) as messages
                FROM person_edges
                GROUP BY person_name
                ORDER BY connections DESC
                LIMIT 10
            """)
            most_connected = [
                {"person_name": r[0], "connections": r[1], "messages": r[2]}
                for r in cur.fetchall()
            ]

            # Least connected (at least 1 edge)
            cur.execute("""
                WITH person_edges AS (
                    SELECT person_a as person_name, message_count
                    FROM communication_edges
                    WHERE week_start > CURRENT_DATE - INTERVAL '28 days'
                    UNION ALL
                    SELECT person_b as person_name, message_count
                    FROM communication_edges
                    WHERE week_start > CURRENT_DATE - INTERVAL '28 days'
                )
                SELECT person_name,
                       COUNT(*) as connections,
                       SUM(message_count) as messages
                FROM person_edges
                GROUP BY person_name
                ORDER BY connections ASC
                LIMIT 10
            """)
            least_connected = [
                {"person_name": r[0], "connections": r[1], "messages": r[2]}
                for r in cur.fetchall()
            ]

            # Channel distribution
            cur.execute("""
                SELECT channel, COUNT(*), SUM(message_count)
                FROM communication_edges
                WHERE week_start > CURRENT_DATE - INTERVAL '28 days'
                GROUP BY channel
                ORDER BY SUM(message_count) DESC
            """)
            channels = [
                {"channel": r[0], "edges": r[1], "messages": r[2]}
                for r in cur.fetchall()
            ]

    return {
        "total_edges": total_edges,
        "total_messages": total_messages,
        "most_connected": most_connected,
        "least_connected": least_connected,
        "channels": channels,
    }


def run_network_analysis() -> dict[str, Any]:
    """Full pipeline: build graph + detect silos + bottlenecks + summary."""
    log.info("network_analysis_start")

    # Build graphs for current and previous weeks
    today = date.today()
    current_week = today - timedelta(days=today.weekday())
    prev_week = current_week - timedelta(days=7)

    graph_current = build_weekly_graph(current_week.isoformat())
    graph_prev = build_weekly_graph(prev_week.isoformat())

    silos = detect_silos()
    bottlenecks = detect_bottlenecks()
    summary = get_network_summary()

    result = {
        "status": "ok",
        "graphs_built": {
            "current_week": graph_current,
            "previous_week": graph_prev,
        },
        "silos": {
            "count": len(silos),
            "items": silos,
        },
        "bottlenecks": {
            "count": len(bottlenecks),
            "items": bottlenecks,
        },
        "summary": summary,
    }

    log.info("network_analysis_complete",
             silos=len(silos), bottlenecks=len(bottlenecks))
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        week = sys.argv[2] if len(sys.argv) > 2 else None
        result = build_weekly_graph(week)
    else:
        result = run_network_analysis()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
