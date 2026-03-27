"""
Relationships API — CRUD for Sebastian's relationship repository.
"""
from __future__ import annotations

import time
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.postgres import get_pg_connection
from app.db.relationships_db import (
    get_person_by_slug,
    get_person_full_profile,
    _person_row_to_dict,
)

router = APIRouter(tags=["relationships"])


# ── Pydantic Schemas ───────────────────────────────────────────────

class RelationshipIn(BaseModel):
    relationship_type: str
    current_role: str | None = None
    organization: str | None = None
    status: str = "active"
    contact_channel: str | None = None
    can_contact_directly: bool = True
    sentiment: str = "neutral"
    last_contact_date: date | None = None
    notes: str | None = None


class PersonCreate(BaseModel):
    slug: str
    first_name: str
    last_name: str | None = None
    aliases: list[str] | None = None
    relationship: RelationshipIn | None = None


class PersonUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    aliases: list[str] | None = None
    relationship: RelationshipIn | None = None


class TimelineEventCreate(BaseModel):
    event_date: date
    event_type: str | None = None
    description: str
    source: str = "manual"


class OpenLoopCreate(BaseModel):
    description: str


class RoleHistoryCreate(BaseModel):
    role: str
    organization: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    notes: str | None = None


# ── Helpers ────────────────────────────────────────────────────────

def _require_person(cur, slug: str) -> dict:
    person = get_person_by_slug(cur, slug)
    if person is None:
        raise HTTPException(status_code=404, detail=f"Person '{slug}' not found")
    return person


# ── Endpoints ──────────────────────────────────────────────────────

@router.get("/people")
def list_people(
    type: str | None = Query(default=None, description="Filter by relationship_type"),
    status: str | None = Query(default=None, description="Filter by status"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    started_at = time.time()

    filters = []
    params: list[Any] = []

    if type:
        filters.append("r.relationship_type = %s")
        params.append(type)
    if status:
        filters.append("r.status = %s")
        params.append(status)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT p.id, p.slug, p.first_name, p.last_name, p.aliases,
                       p.created_at, p.updated_at,
                       r.id, r.relationship_type, r.person_role, r.organization,
                       r.status, r.contact_channel, r.can_contact_directly, r.sentiment,
                       r.last_contact_date, r.notes,
                       r.created_at, r.updated_at
                FROM people p
                LEFT JOIN relationships r ON r.person_id = p.id
                {where}
                ORDER BY p.first_name, p.last_name
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()

    people = [_person_row_to_dict(row) for row in rows]
    latency_ms = int((time.time() - started_at) * 1000)

    return {
        "people": people,
        "meta": {"count": len(people), "latency_ms": latency_ms},
    }


@router.post("/people", status_code=201)
def create_person(body: PersonCreate) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Check slug uniqueness
            cur.execute("SELECT COUNT(*) FROM people WHERE slug = %s", (body.slug,))
            row = cur.fetchone()
            if row and row[0] > 0:
                raise HTTPException(status_code=409, detail=f"Person with slug '{body.slug}' already exists")

            aliases = body.aliases or []
            cur.execute(
                """
                INSERT INTO people (slug, first_name, last_name, aliases)
                VALUES (%s, %s, %s, %s)
                RETURNING id, slug, first_name, last_name, aliases, created_at, updated_at
                """,
                (body.slug, body.first_name, body.last_name, aliases),
            )
            p = cur.fetchone()
            person_id = p[0]

            rel_data = None
            if body.relationship:
                r = body.relationship
                cur.execute(
                    """
                    INSERT INTO relationships
                        (person_id, relationship_type, person_role, organization,
                         status, contact_channel, can_contact_directly, sentiment,
                         last_contact_date, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, relationship_type, person_role, organization,
                              status, contact_channel, can_contact_directly, sentiment,
                              last_contact_date, notes, created_at, updated_at
                    """,
                    (person_id, r.relationship_type, r.person_role, r.organization,
                     r.status, r.contact_channel, r.can_contact_directly, r.sentiment,
                     r.last_contact_date, r.notes),
                )
                rr = cur.fetchone()
                rel_data = {
                    "id": rr[0], "relationship_type": rr[1], "current_role": rr[2],
                    "organization": rr[3], "status": rr[4], "contact_channel": rr[5],
                    "can_contact_directly": rr[6], "sentiment": rr[7],
                    "last_contact_date": str(rr[8]) if rr[8] else None,
                    "notes": rr[9], "created_at": str(rr[10]), "updated_at": str(rr[11]),
                }

            conn.commit()

    return {
        "id": p[0], "slug": p[1], "first_name": p[2], "last_name": p[3],
        "aliases": list(p[4]) if p[4] else [],
        "created_at": str(p[5]), "updated_at": str(p[6]),
        "relationship": rel_data,
    }


@router.get("/people/{slug}")
def get_person(slug: str) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            person = _require_person(cur, slug)
            extras = get_person_full_profile(cur, person["id"])

    return {**person, **extras}


@router.put("/people/{slug}")
def update_person(slug: str, body: PersonUpdate) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            person = _require_person(cur, slug)
            person_id = person["id"]

            # Update people table
            updates = []
            params: list[Any] = []

            if body.first_name is not None:
                updates.append("first_name = %s")
                params.append(body.first_name)
            if body.last_name is not None:
                updates.append("last_name = %s")
                params.append(body.last_name)
            if body.aliases is not None:
                updates.append("aliases = %s")
                params.append(body.aliases)

            if updates:
                updates.append("updated_at = NOW()")
                params.append(person_id)
                cur.execute(  # safe: f-string for column names only, values via %s
                    f"UPDATE people SET {', '.join(updates)} WHERE id = %s",
                    params,
                )

            # Update relationships table
            if body.relationship:
                r = body.relationship
                rel_updates = [
                    "relationship_type = %s", "person_role = %s", "organization = %s",
                    "status = %s", "contact_channel = %s", "can_contact_directly = %s",
                    "sentiment = %s", "last_contact_date = %s", "notes = %s",
                    "updated_at = NOW()",
                ]
                rel_params = [
                    r.relationship_type, r.person_role, r.organization,
                    r.status, r.contact_channel, r.can_contact_directly,
                    r.sentiment, r.last_contact_date, r.notes, person_id,
                ]
                # Upsert
                cur.execute("SELECT id FROM relationships WHERE person_id = %s", (person_id,))
                if cur.fetchone():
                    cur.execute(  # safe: f-string for column names only, values via %s
                        f"UPDATE relationships SET {', '.join(rel_updates)} WHERE person_id = %s",
                        rel_params,
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO relationships
                            (person_id, relationship_type, person_role, organization,
                             status, contact_channel, can_contact_directly, sentiment,
                             last_contact_date, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        [person_id] + rel_params[:-1],
                    )

            conn.commit()
            updated = get_person_by_slug(cur, slug)

    return updated


@router.delete("/people/{slug}")
def delete_person(slug: str) -> dict[str, str]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            person = _require_person(cur, slug)
            cur.execute("DELETE FROM people WHERE id = %s", (person["id"],))
            conn.commit()
    return {"deleted": slug}


@router.post("/people/{slug}/timeline", status_code=201)
def add_timeline_event(slug: str, body: TimelineEventCreate) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            person = _require_person(cur, slug)
            cur.execute(
                """
                INSERT INTO relationship_timeline
                    (person_id, event_date, event_type, description, source)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, event_date, event_type, description, source, created_at
                """,
                (person["id"], body.event_date, body.event_type, body.description, body.source),
            )
            row = cur.fetchone()
            conn.commit()

    return {
        "id": row[0], "person_slug": slug,
        "event_date": str(row[1]), "event_type": row[2],
        "description": row[3], "source": row[4], "created_at": str(row[5]),
    }


@router.post("/people/{slug}/loops", status_code=201)
def add_open_loop(slug: str, body: OpenLoopCreate) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            person = _require_person(cur, slug)
            cur.execute(
                """
                INSERT INTO relationship_open_loops (person_id, description)
                VALUES (%s, %s)
                RETURNING id, description, status, created_at, closed_at
                """,
                (person["id"], body.description),
            )
            row = cur.fetchone()
            conn.commit()

    return {
        "id": row[0], "person_slug": slug,
        "description": row[1], "status": row[2],
        "created_at": str(row[3]),
        "closed_at": str(row[4]) if row[4] else None,
    }


@router.put("/people/{slug}/loops/{loop_id}")
def close_open_loop(slug: str, loop_id: int) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            person = _require_person(cur, slug)
            cur.execute(
                "SELECT id FROM relationship_open_loops WHERE id = %s AND person_id = %s",
                (loop_id, person["id"]),
            )
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail=f"Open loop {loop_id} not found for '{slug}'")

            cur.execute(
                """
                UPDATE relationship_open_loops
                SET status = 'closed', closed_at = NOW()
                WHERE id = %s
                RETURNING id, description, status, created_at, closed_at
                """,
                (loop_id,),
            )
            row = cur.fetchone()
            conn.commit()

    return {
        "id": row[0], "person_slug": slug,
        "description": row[1], "status": row[2],
        "created_at": str(row[3]),
        "closed_at": str(row[4]) if row[4] else None,
    }


@router.post("/people/{slug}/roles", status_code=201)
def add_role_history(slug: str, body: RoleHistoryCreate) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            person = _require_person(cur, slug)
            cur.execute(
                """
                INSERT INTO relationship_roles_history
                    (person_id, role, organization, date_from, date_to, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, role, organization, date_from, date_to, notes
                """,
                (person["id"], body.role, body.organization, body.date_from, body.date_to, body.notes),
            )
            row = cur.fetchone()
            conn.commit()

    return {
        "id": row[0], "person_slug": slug,
        "role": row[1], "organization": row[2],
        "date_from": str(row[3]) if row[3] else None,
        "date_to": str(row[4]) if row[4] else None,
        "notes": row[5],
    }
