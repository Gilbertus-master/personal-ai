"""Universal Interaction Layer — activity log & item annotations API."""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.db.postgres import get_pg_connection
from app.retrieval.answering import answer_question
from app.retrieval.retriever import search_chunks

log = logging.getLogger(__name__)

router = APIRouter(tags=["activity"])


# --------------- Schemas ---------------

class ActivityLogRequest(BaseModel):
    action_type: str = Field(description="research/comment/rate/task/flag/forward/view")
    item_id: str
    item_type: str
    item_title: str | None = None
    item_context: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AnnotateRequest(BaseModel):
    item_id: str
    item_type: str
    annotation_type: str
    content: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    is_false_positive: bool = False
    forward_to: str | None = None


class ResearchRequest(BaseModel):
    item_id: str
    item_type: str
    item_title: str
    item_content: str | None = None
    context: str | None = None


# --------------- Endpoints ---------------

@router.post("/activity/log")
def log_activity(req: ActivityLogRequest) -> dict:
    """Log a user action on an item."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_activity_log
                   (action_type, item_id, item_type, item_title, item_context, payload)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id, created_at""",
                (
                    req.action_type,
                    req.item_id,
                    req.item_type,
                    req.item_title,
                    req.item_context,
                    json.dumps(req.payload),
                ),
            )
            row = cur.fetchone()
            conn.commit()
    return {"id": row[0], "created_at": row[1].isoformat()}


@router.get("/activity/log")
def get_activity_log(
    user_id: str = Query(default="sebastian"),
    limit: int = Query(default=50, ge=1, le=500),
    action_type: str | None = Query(default=None),
) -> list[dict]:
    """Get activity log entries."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            sql = """SELECT id, user_id, action_type, item_id, item_type,
                            item_title, item_context, payload, created_at
                     FROM user_activity_log
                     WHERE user_id = %s"""
            params: list[Any] = [user_id]
            if action_type:
                sql += " AND action_type = %s"
                params.append(action_type)
            sql += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    return [
        {c: (v.isoformat() if hasattr(v, "isoformat") else v) for c, v in zip(cols, r)}
        for r in rows
    ]


@router.post("/items/annotate")
def annotate_item(req: AnnotateRequest) -> dict:
    """Add an annotation (comment, rating, flag, etc.) to an item."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO item_annotations
                   (item_id, item_type, annotation_type, content, rating,
                    is_false_positive, forward_to)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING id, created_at""",
                (
                    req.item_id,
                    req.item_type,
                    req.annotation_type,
                    req.content,
                    req.rating,
                    req.is_false_positive,
                    req.forward_to,
                ),
            )
            row = cur.fetchone()
            conn.commit()
    return {"id": row[0], "created_at": row[1].isoformat()}


@router.get("/items/{item_type}/{item_id}/annotations")
def get_annotations(item_type: str, item_id: str) -> list[dict]:
    """Get all annotations for an item."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, item_id, item_type, user_id, annotation_type,
                          content, rating, is_false_positive, research_result,
                          forward_to, created_at
                   FROM item_annotations
                   WHERE item_type = %s AND item_id = %s
                   ORDER BY created_at DESC""",
                (item_type, item_id),
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    return [
        {c: (v.isoformat() if hasattr(v, "isoformat") else v) for c, v in zip(cols, r)}
        for r in rows
    ]


@router.post("/items/research")
def research_item(req: ResearchRequest) -> dict:
    """Run a deep research query on an item and save the result as annotation."""
    prompt = f"""Przeanalizuj dogłębnie następujący element ({req.item_type}):

Tytuł: {req.item_title}
Kontekst: {req.context or 'brak'}
Treść: {req.item_content or 'brak dodatkowej treści'}

Podaj:
1. Kluczowe fakty i kontekst z dostępnych danych
2. Powiązane osoby, firmy, wydarzenia
3. Potencjalne ryzyka i szanse
4. Rekomendowane następne kroki

Odpowiedz po polsku, zwięźle ale wyczerpująco."""

    try:
        matches = search_chunks(prompt, top_k=8)
        answer = answer_question(prompt, matches)
        research_result = answer if isinstance(answer, str) else answer.get("answer", str(answer))
    except Exception as e:
        log.error("Research failed for %s/%s: %s", req.item_type, req.item_id, e)
        raise HTTPException(status_code=500, detail=f"Research failed: {e}")

    # Save as annotation
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO item_annotations
                   (item_id, item_type, annotation_type, content, research_result)
                   VALUES (%s, %s, 'research', %s, %s)
                   RETURNING id, created_at""",
                (req.item_id, req.item_type, req.item_title, research_result),
            )
            row = cur.fetchone()
            conn.commit()

    # Log activity
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_activity_log
                   (action_type, item_id, item_type, item_title, item_context)
                   VALUES ('research', %s, %s, %s, %s)""",
                (req.item_id, req.item_type, req.item_title, req.context),
            )
            conn.commit()

    return {"id": row[0], "research_result": research_result}
