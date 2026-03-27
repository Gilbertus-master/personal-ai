"""
Knowledge Blind Spot Detector — detects what Gilbertus doesn't know about.

Identifies:
- Unknown persons: frequently mentioned but not in people table
- Undocumented projects: project entities with very few chunks
- Source gaps: data sources that stopped providing data unexpectedly
- Topic gaps: frequently mentioned topics without related documents

All SQL-based, no LLM needed.
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

log = structlog.get_logger(__name__)


def detect_unknown_persons(min_mentions: int = 5) -> list[dict[str, Any]]:
    """Find entities of type 'person' mentioned >N times but NOT in people table."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT en.canonical_name, en.name, COUNT(DISTINCT ce.chunk_id) as mentions
                FROM entities en
                JOIN chunk_entities ce ON ce.entity_id = en.id
                WHERE en.entity_type = 'person'
                  AND NOT EXISTS (
                      SELECT 1 FROM people p
                      WHERE LOWER(p.first_name || ' ' || COALESCE(p.last_name, ''))
                            = LOWER(COALESCE(en.canonical_name, en.name))
                         OR LOWER(COALESCE(en.canonical_name, en.name)) = ANY(
                             SELECT LOWER(unnest(p.aliases)) FROM people p2
                             WHERE p2.id = p.id
                         )
                  )
                GROUP BY en.canonical_name, en.name
                HAVING COUNT(DISTINCT ce.chunk_id) > %s
                ORDER BY mentions DESC
                LIMIT 30
            """, (min_mentions,))
            rows = cur.fetchall()

    return [
        {
            "canonical_name": r[0] or r[1],
            "raw_name": r[1],
            "mentions": r[2],
            "recommendation": "Add to people table for tracking",
        }
        for r in rows
    ]


def detect_undocumented_projects(max_chunks: int = 3) -> list[dict[str, Any]]:
    """Find project entities with mentions but very few associated chunks."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COALESCE(en.canonical_name, en.name) as project_name,
                    COUNT(DISTINCT ce.chunk_id) as chunk_count,
                    COUNT(DISTINCT ev.id) as event_count
                FROM entities en
                LEFT JOIN chunk_entities ce ON ce.entity_id = en.id
                LEFT JOIN event_entities ee ON ee.entity_id = en.id
                LEFT JOIN events ev ON ev.id = ee.event_id
                WHERE en.entity_type = 'project'
                GROUP BY en.canonical_name, en.name
                HAVING COUNT(DISTINCT ce.chunk_id) <= %s
                   AND (COUNT(DISTINCT ev.id) > 0 OR COUNT(DISTINCT ce.chunk_id) > 0)
                ORDER BY event_count DESC, chunk_count DESC
                LIMIT 20
            """, (max_chunks,))
            rows = cur.fetchall()

    return [
        {
            "project_name": r[0],
            "chunk_count": r[1],
            "event_count": r[2],
            "recommendation": "Gather more documentation about this project",
        }
        for r in rows
    ]


def detect_source_gaps(gap_hours: int = 48) -> list[dict[str, Any]]:
    """Find sources that haven't provided new data in >N hours (unexpected gap)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.source_type,
                       MAX(d.created_at) as last_doc,
                       EXTRACT(HOURS FROM NOW() - MAX(d.created_at)) as hours_ago,
                       COUNT(d.id) as total_docs
                FROM sources s
                JOIN documents d ON d.source_id = s.id
                GROUP BY s.source_type
                HAVING MAX(d.created_at) < NOW() - INTERVAL '%s hours'
                ORDER BY hours_ago DESC
            """, (gap_hours,))
            rows = cur.fetchall()

    return [
        {
            "source_type": r[0],
            "last_document": str(r[1]) if r[1] else None,
            "hours_since_last": round(float(r[2]), 1) if r[2] else None,
            "total_documents": r[3],
            "recommendation": f"Check if {r[0]} sync is working",
        }
        for r in rows
    ]


def detect_topic_gaps() -> list[dict[str, Any]]:
    """Find topics frequently mentioned in events but with no related documents.

    A 'topic gap' is an event_type or subject that appears often in events
    but has very few associated document chunks.
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Find entities mentioned in many events but few chunks
            cur.execute("""
                SELECT
                    COALESCE(en.canonical_name, en.name) as topic,
                    en.entity_type,
                    COUNT(DISTINCT ee.event_id) as event_mentions,
                    COUNT(DISTINCT ce.chunk_id) as chunk_mentions
                FROM entities en
                JOIN event_entities ee ON ee.entity_id = en.id
                LEFT JOIN chunk_entities ce ON ce.entity_id = en.id
                WHERE en.entity_type IN ('organization', 'project', 'topic')
                GROUP BY en.canonical_name, en.name, en.entity_type
                HAVING COUNT(DISTINCT ee.event_id) >= 3
                   AND COUNT(DISTINCT ce.chunk_id) < 2
                ORDER BY event_mentions DESC
                LIMIT 20
            """)
            rows = cur.fetchall()

    return [
        {
            "topic": r[0],
            "entity_type": r[1],
            "event_mentions": r[2],
            "chunk_mentions": r[3],
            "recommendation": "Topic discussed in events but lacks documentation",
        }
        for r in rows
    ]


def run_blind_spot_scan() -> dict[str, Any]:
    """Run all detectors, return consolidated report."""
    log.info("blind_spot_scan_start")

    unknown_persons = detect_unknown_persons()
    undocumented_projects = detect_undocumented_projects()
    source_gaps = detect_source_gaps()
    topic_gaps = detect_topic_gaps()

    total_issues = (
        len(unknown_persons) + len(undocumented_projects)
        + len(source_gaps) + len(topic_gaps)
    )

    result = {
        "status": "ok",
        "total_blind_spots": total_issues,
        "unknown_persons": {
            "count": len(unknown_persons),
            "items": unknown_persons,
        },
        "undocumented_projects": {
            "count": len(undocumented_projects),
            "items": undocumented_projects,
        },
        "source_gaps": {
            "count": len(source_gaps),
            "items": source_gaps,
        },
        "topic_gaps": {
            "count": len(topic_gaps),
            "items": topic_gaps,
        },
    }

    log.info("blind_spot_scan_complete",
             total=total_issues,
             persons=len(unknown_persons),
             projects=len(undocumented_projects),
             sources=len(source_gaps),
             topics=len(topic_gaps))
    return result


if __name__ == "__main__":
    result = run_blind_spot_scan()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
