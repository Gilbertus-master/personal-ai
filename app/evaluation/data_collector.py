"""
Collect all data about a person for evaluation.

Given a person slug or entity_id, gather:
- All chunks mentioning the person (via chunk_entities)
- All events involving the person (via event_entities)
- Relationship metadata (role, org, sentiment)
- Open loops
- Communication volume by month
"""
from __future__ import annotations

from typing import Any

from app.db.postgres import get_pg_connection


def collect_person_data(
    person_slug: str | None = None,
    entity_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    max_chunks: int = 200,
    max_events: int = 500,
) -> dict[str, Any]:
    """Collect all evaluation-relevant data for a person."""

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Resolve person
            if person_slug and not entity_id:
                cur.execute("""
                    SELECT p.id, p.first_name, p.last_name, p.entity_id,
                           r.person_role, r.organization, r.status, r.sentiment
                    FROM people p
                    LEFT JOIN relationships r ON r.person_id = p.id
                    WHERE p.slug = %s
                    LIMIT 1
                """, (person_slug,))
                rows = cur.fetchall()
                if not rows:
                    # Try name match
                    parts = person_slug.replace("-", " ").split()
                    if len(parts) >= 2:
                        cur.execute("""
                            SELECT p.id, p.first_name, p.last_name, p.entity_id,
                                   r.person_role, r.organization, r.status, r.sentiment
                            FROM people p
                            LEFT JOIN relationships r ON r.person_id = p.id
                            WHERE LOWER(p.first_name) = LOWER(%s) AND LOWER(p.last_name) = LOWER(%s)
                            LIMIT 1
                        """, (parts[0], parts[-1]))
                        rows = cur.fetchall()
                if not rows:
                    return {"error": f"Person not found: {person_slug}"}
                person_id, first, last, entity_id, role, org, status, sentiment = rows[0]
            elif entity_id:
                cur.execute("""
                    SELECT p.id, p.first_name, p.last_name, p.entity_id,
                           r.person_role, r.organization, r.status, r.sentiment
                    FROM people p
                    LEFT JOIN relationships r ON r.person_id = p.id
                    WHERE p.entity_id = %s
                    LIMIT 1
                """, (entity_id,))
                rows = cur.fetchall()
                if not rows:
                    return {"error": f"Person not found for entity_id: {entity_id}"}
                person_id, first, last, entity_id, role, org, status, sentiment = rows[0]
            else:
                return {"error": "Provide person_slug or entity_id"}

            # Date filter
            date_clause = ""
            date_params: list = []
            if date_from:
                date_clause += " AND e.event_time >= %s::timestamptz"
                date_params.append(date_from)
            if date_to:
                date_clause += " AND e.event_time < %s::timestamptz"
                date_params.append(date_to)

            # Events involving this person
            cur.execute(f"""
                SELECT e.event_type, e.event_time, e.summary, e.confidence
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                WHERE ee.entity_id = %s
                  AND e.event_time IS NOT NULL
                  {date_clause}
                ORDER BY e.event_time DESC
                LIMIT %s
            """, [entity_id] + date_params + [max_events])
            events = [
                {"type": r[0], "time": r[1].isoformat() if r[1] else None, "summary": r[2], "confidence": float(r[3]) if r[3] else 0}
                for r in cur.fetchall()
            ]

            # Chunks mentioning this person (most relevant text excerpts)
            chunk_date_clause = ""
            chunk_params: list = []
            if date_from:
                chunk_date_clause += " AND d.created_at >= %s::timestamptz"
                chunk_params.append(date_from)
            if date_to:
                chunk_date_clause += " AND d.created_at < %s::timestamptz"
                chunk_params.append(date_to)

            cur.execute(f"""
                SELECT LEFT(c.text, 500), s.source_type, d.created_at
                FROM chunks c
                JOIN chunk_entities ce ON ce.chunk_id = c.id
                JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE ce.entity_id = %s
                  {chunk_date_clause}
                ORDER BY d.created_at DESC
                LIMIT %s
            """, [entity_id] + chunk_params + [max_chunks])
            chunks = [
                {"text": r[0], "source": r[1], "date": r[2].isoformat() if r[2] else None}
                for r in cur.fetchall()
            ]

            # Event type breakdown
            cur.execute(f"""
                SELECT e.event_type, COUNT(*) as cnt
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                WHERE ee.entity_id = %s AND e.event_time IS NOT NULL {date_clause}
                GROUP BY e.event_type ORDER BY cnt DESC
            """, [entity_id] + date_params)
            event_breakdown = {r[0]: r[1] for r in cur.fetchall()}

            # Monthly activity
            cur.execute(f"""
                SELECT DATE_TRUNC('month', e.event_time) as month, COUNT(*) as cnt
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                WHERE ee.entity_id = %s AND e.event_time IS NOT NULL {date_clause}
                GROUP BY month ORDER BY month
            """, [entity_id] + date_params)
            monthly = [
                {"month": r[0].strftime("%Y-%m") if r[0] else "?", "events": r[1]}
                for r in cur.fetchall()
            ]

            # Open loops
            try:
                cur.execute("""
                    SELECT description, status FROM relationship_open_loops
                    WHERE person_id = %s AND status = 'open'
                """, (person_id,))
                open_loops = [{"description": r[0]} for r in cur.fetchall()]
            except Exception:
                open_loops = []

    # Enrich with Omnius data (if available)
    omnius_data = _collect_omnius_data(f"{first} {last}", org, date_from, date_to)

    return {
        "person": {
            "name": f"{first} {last}",
            "slug": person_slug,
            "entity_id": entity_id,
            "role": role,
            "organization": org,
            "status": status,
            "sentiment": sentiment,
        },
        "period": {"from": date_from, "to": date_to},
        "stats": {
            "total_events": len(events),
            "total_chunks": len(chunks),
            "event_type_breakdown": event_breakdown,
            "monthly_activity": monthly,
        },
        "events": events,
        "chunks": chunks,
        "open_loops": open_loops,
        "omnius_data": omnius_data,
    }


def _collect_omnius_data(person_name: str, organization: str | None, date_from: str | None, date_to: str | None) -> dict[str, Any] | None:
    """Try to pull additional data from Omnius tenant for multi-perspective evaluation."""
    try:
        from app.omnius.client import get_omnius, list_tenants

        tenants = list_tenants()
        if not tenants:
            return None

        # Find matching tenant by organization
        tenant = None
        if organization:
            org_lower = organization.lower()
            if "reh" in org_lower or "holding" in org_lower or "respect energy h" in org_lower:
                tenant = "reh"
            elif "ref" in org_lower or "fuels" in org_lower:
                tenant = "ref"

        if not tenant and tenants:
            tenant = tenants[0]

        client = get_omnius(tenant)

        # Ask Omnius about this person
        query = f"Podsumuj aktywność {person_name} w okresie {date_from or '?'} - {date_to or '?'}. Uwzględnij: komunikację, realizację zadań, udział w projektach, response time."
        result = client.ask(query, answer_length="long")

        return {
            "tenant": tenant,
            "perspective": "corporate",
            "summary": result.get("answer", ""),
            "source": f"Omnius {tenant.upper()}",
        }
    except Exception:
        return None
