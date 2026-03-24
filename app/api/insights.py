"""
Insights — browse and summarize extracted insights from the archive.
"""
from __future__ import annotations

import os
import time
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.db.postgres import get_pg_connection

load_dotenv()

router = APIRouter(tags=["insights"])

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


# ── Schemas ────────────────────────────────────────────────────────

class InsightItem(BaseModel):
    id: int
    insight_type: str | None
    area: str | None
    title: str | None
    description: str | None
    evidence: str | None
    confidence: float | None
    created_at: str | None
    reviewed: bool | None


class InsightsListResponse(BaseModel):
    insights: list[InsightItem]
    meta: dict[str, Any]


class InsightsSummaryResponse(BaseModel):
    summary: str
    meta: dict[str, Any]


# ── Endpoints ──────────────────────────────────────────────────────

@router.get("/insights", response_model=InsightsListResponse)
def list_insights(
    area: str | None = Query(default=None, description="Filter by area"),
    insight_type: str | None = Query(default=None, alias="type", description="Filter by insight_type"),
    limit: int = Query(default=50, ge=1, le=500),
) -> InsightsListResponse:
    started_at = time.time()

    conditions: list[str] = []
    params: list[Any] = []

    if area:
        conditions.append("area = %s")
        params.append(area)
    if insight_type:
        conditions.append("insight_type = %s")
        params.append(insight_type)

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT id, insight_type, area, title, description, evidence, confidence, created_at, reviewed
        FROM insights
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %s
    """
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

    insights = [
        InsightItem(
            id=r[0],
            insight_type=r[1],
            area=r[2],
            title=r[3],
            description=r[4],
            evidence=r[5],
            confidence=float(r[6]) if r[6] is not None else None,
            created_at=str(r[7]) if r[7] is not None else None,
            reviewed=r[8],
        )
        for r in rows
    ]

    latency_ms = int((time.time() - started_at) * 1000)
    return InsightsListResponse(
        insights=insights,
        meta={
            "count": len(insights),
            "area": area,
            "insight_type": insight_type,
            "latency_ms": latency_ms,
        },
    )


@router.get("/insights/summary", response_model=InsightsSummaryResponse)
def insights_summary(
    area: str | None = Query(default=None, description="Filter by area before summarizing"),
    insight_type: str | None = Query(default=None, alias="type", description="Filter by insight_type"),
    limit: int = Query(default=100, ge=1, le=500, description="Max insights to feed into summary"),
) -> InsightsSummaryResponse:
    """Claude-powered executive summary of recent insights."""
    started_at = time.time()

    conditions: list[str] = []
    params: list[Any] = []

    if area:
        conditions.append("area = %s")
        params.append(area)
    if insight_type:
        conditions.append("insight_type = %s")
        params.append(insight_type)

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT insight_type, area, title, description, evidence, confidence, created_at
        FROM insights
        {where_clause}
        ORDER BY created_at DESC
        LIMIT %s
    """
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

    if not rows:
        return InsightsSummaryResponse(
            summary="Brak insightow do podsumowania.",
            meta={"insight_count": 0, "latency_ms": int((time.time() - started_at) * 1000)},
        )

    parts: list[str] = []
    for r in rows:
        parts.append(
            f"- [{r[0] or 'unknown'}] ({r[1] or 'general'}) {r[2] or 'Untitled'}\n"
            f"  {r[3] or ''}\n"
            f"  Dowody: {r[4] or 'brak'} | Pewnosc: {float(r[5]):.0%} | Data: {r[6]}"
            if r[5] is not None
            else f"- [{r[0] or 'unknown'}] ({r[1] or 'general'}) {r[2] or 'Untitled'}\n"
            f"  {r[3] or ''}\n"
            f"  Dowody: {r[4] or 'brak'} | Data: {r[6]}"
        )

    prompt_data = "\n".join(parts)

    client = Anthropic()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": (
                    "Jestes osobistym doradca analitycznym Sebastiana. "
                    "Ponizej znajduje sie lista insightow wyekstrahowanych z jego archiwum. "
                    "Przygotuj zwiezle podsumowanie wykonawcze (executive summary) w jezyku polskim.\n\n"
                    "Skup sie na:\n"
                    "- Najwazniejszych wnioskach i trendach\n"
                    "- Obszarach wymagajacych uwagi\n"
                    "- Powtarzajacych sie wzorcach\n"
                    "- Rekomendacjach\n\n"
                    f"Insighty ({len(rows)} szt.):\n\n"
                    f"{prompt_data}\n\n"
                    "Odpowiedz czytelnie, zwiezle, z naglowkami."
                ),
            }
        ],
    )

    summary_text = response.content[0].text
    latency_ms = int((time.time() - started_at) * 1000)

    return InsightsSummaryResponse(
        summary=summary_text,
        meta={
            "insight_count": len(rows),
            "area": area,
            "insight_type": insight_type,
            "latency_ms": latency_ms,
        },
    )
