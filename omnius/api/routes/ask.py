"""Omnius /ask endpoint — RBAC-aware corporate data search."""
from __future__ import annotations

import os
import time

import structlog
from anthropic import Anthropic
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from omnius.api.rbac import require_permission
from omnius.core.permissions import allowed_classifications
from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)
router = APIRouter(tags=["ask"])

ANTHROPIC_MODEL = os.getenv("OMNIUS_LLM_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = (
    "Jesteś Omnius, korporacyjny asystent AI dla {company}. "
    "Odpowiadaj profesjonalnie, konkretnie i na podstawie dostarczonych danych. "
    "Jeśli nie masz wystarczających danych, powiedz to wprost. "
    "Formatuj odpowiedzi w Markdown."
)

COMPANY_NAME = os.getenv("OMNIUS_COMPANY_NAME", "Respect Energy Fuels")


class AskRequest(BaseModel):
    query: str
    answer_length: str = Field(default="medium", pattern="^(short|medium|long)$")


class AskResponse(BaseModel):
    answer: str
    sources_count: int
    latency_ms: int


@router.post("/ask", response_model=AskResponse)
@require_permission("data:read:own")
async def ask(request: Request, body: AskRequest, user: dict = None):
    """Query corporate data with classification-aware filtering."""
    started_at = time.time()

    # Get allowed classification levels for this user's role
    classifications = allowed_classifications(user["role_name"])

    # Operator has no data access — explicit block
    if not classifications:
        return AskResponse(
            answer="Brak uprawnień do danych biznesowych. Skontaktuj się z CEO.",
            sources_count=0,
            latency_ms=0,
        )

    # Full-text search with classification + ownership + department filter
    user_id = user.get("user_id")
    department = user.get("department")
    role_name = user["role_name"]

    # Try Qdrant semantic search first, fall back to PostgreSQL FTS
    matches = []
    search_method = "fts"

    try:
        from omnius.sync.embeddings import search_vectors
        vector_results = search_vectors(
            query=body.query,
            classifications=classifications,
            user_id=user_id,
            department=department if role_name in ("director", "manager", "specialist") else None,
            limit=15,
        )
        if vector_results:
            matches = [(r["chunk_id"], r["content"], r["title"], r["source_type"], r["classification"])
                       for r in vector_results]
            search_method = "vector"
    except Exception as e:
        log.debug("qdrant_unavailable_falling_back_to_fts", error=str(e))

    # Fallback: PostgreSQL full-text search
    if not matches:
        dept_filter = ""
        dept_params: list = []
        if role_name in ("director", "manager", "specialist") and department:
            dept_filter = "AND (d.department IS NULL OR d.department = %s)"
            dept_params = [department]

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT c.id, c.content, d.title, d.source_type, c.classification
                    FROM omnius_chunks c
                    JOIN omnius_documents d ON d.id = c.document_id
                    WHERE c.classification = ANY(%s)
                      AND (d.owner_user_id IS NULL
                           OR d.owner_user_id = %s
                           OR c.classification != 'personal')
                      {dept_filter}
                      AND to_tsvector('simple', c.content) @@ plainto_tsquery('simple', %s)
                    ORDER BY ts_rank(to_tsvector('simple', c.content),
                                     plainto_tsquery('simple', %s)) DESC
                    LIMIT 15
                """, (classifications, user_id, *dept_params, body.query, body.query))
                matches = cur.fetchall()
        search_method = "fts"

    if not matches:
        return AskResponse(
            answer="Nie znalazłem wystarczających danych dla tego pytania.",
            sources_count=0,
            latency_ms=int((time.time() - started_at) * 1000),
        )

    # Build context for LLM
    context_parts = []
    for row in matches:
        src_label = f"[{row[3]}] {row[2] or 'Untitled'}"
        context_parts.append(f"--- {src_label} ---\n{row[1][:2000]}")

    context = "\n\n".join(context_parts)

    max_tokens = {"short": 300, "medium": 800, "long": 2000}.get(body.answer_length, 800)

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT.format(company=COMPANY_NAME),
        messages=[{
            "role": "user",
            "content": f"Kontekst z danych firmowych:\n\n{context}\n\n---\nPytanie: {body.query}",
        }],
    )

    answer = response.content[0].text
    latency_ms = int((time.time() - started_at) * 1000)

    log.info("omnius_ask", user=user.get("email", user.get("api_key_name")),
             query=body.query[:100], matches=len(matches), latency_ms=latency_ms,
             search=search_method)

    return AskResponse(answer=answer, sources_count=len(matches), latency_ms=latency_ms)
