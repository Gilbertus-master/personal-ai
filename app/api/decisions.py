"""
Decision journal — log decisions, track outcomes, analyze patterns.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.postgres import get_pg_connection

load_dotenv()

router = APIRouter(tags=["decisions"])

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


# ── Schemas ────────────────────────────────────────────────────────

class DecisionCreate(BaseModel):
    decision_text: str
    context: str | None = None
    expected_outcome: str | None = None
    area: str = Field(default="general", pattern="^(business|trading|relationships|wellbeing|general)$")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    decided_at: datetime | None = None


class DecisionResponse(BaseModel):
    id: int
    decision_text: str
    context: str | None
    expected_outcome: str | None
    area: str
    confidence: float
    decided_at: str
    created_at: str


class OutcomeCreate(BaseModel):
    actual_outcome: str
    rating: int = Field(..., ge=1, le=5)
    outcome_date: datetime | None = None


class OutcomeResponse(BaseModel):
    id: int
    decision_id: int
    actual_outcome: str
    rating: int
    outcome_date: str
    created_at: str


class DecisionWithOutcomes(BaseModel):
    id: int
    decision_text: str
    context: str | None
    expected_outcome: str | None
    area: str
    confidence: float
    decided_at: str
    created_at: str
    outcomes: list[OutcomeResponse]


class DecisionsListResponse(BaseModel):
    decisions: list[DecisionWithOutcomes]
    meta: dict[str, Any]


class PatternsResponse(BaseModel):
    insights: str
    meta: dict[str, Any]


# ── Endpoints ──────────────────────────────────────────────────────

@router.post("/decision", response_model=DecisionResponse)
def create_decision(body: DecisionCreate) -> DecisionResponse:
    decided_at = body.decided_at or datetime.now(tz=timezone.utc)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO decisions (decision_text, context, expected_outcome, area, confidence, decided_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, decision_text, context, expected_outcome, area, confidence, decided_at, created_at
                """,
                (body.decision_text, body.context, body.expected_outcome, body.area, body.confidence, decided_at),
            )
            row = cur.fetchone()
            conn.commit()

    return DecisionResponse(
        id=row[0],
        decision_text=row[1],
        context=row[2],
        expected_outcome=row[3],
        area=row[4],
        confidence=float(row[5]),
        decided_at=str(row[6]),
        created_at=str(row[7]),
    )


@router.post("/decision/{decision_id}/outcome", response_model=OutcomeResponse)
def create_outcome(decision_id: int, body: OutcomeCreate) -> OutcomeResponse:
    outcome_date = body.outcome_date or datetime.now(tz=timezone.utc)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM decisions WHERE id = %s", (decision_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")

            cur.execute(
                """
                INSERT INTO decision_outcomes (decision_id, actual_outcome, rating, outcome_date)
                VALUES (%s, %s, %s, %s)
                RETURNING id, decision_id, actual_outcome, rating, outcome_date, created_at
                """,
                (decision_id, body.actual_outcome, body.rating, outcome_date),
            )
            row = cur.fetchone()
            conn.commit()

    return OutcomeResponse(
        id=row[0],
        decision_id=row[1],
        actual_outcome=row[2],
        rating=row[3],
        outcome_date=str(row[4]),
        created_at=str(row[5]),
    )


@router.get("/decisions", response_model=DecisionsListResponse)
def list_decisions(
    area: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> DecisionsListResponse:
    started_at = time.time()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if area:
                cur.execute(
                    """
                    SELECT id, decision_text, context, expected_outcome, area, confidence, decided_at, created_at
                    FROM decisions
                    WHERE area = %s
                    ORDER BY decided_at DESC
                    LIMIT %s
                    """,
                    (area, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, decision_text, context, expected_outcome, area, confidence, decided_at, created_at
                    FROM decisions
                    ORDER BY decided_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            decision_rows = cur.fetchall()

            if not decision_rows:
                return DecisionsListResponse(
                    decisions=[],
                    meta={"count": 0, "latency_ms": int((time.time() - started_at) * 1000)},
                )

            decision_ids = [r[0] for r in decision_rows]
            cur.execute(
                """
                SELECT id, decision_id, actual_outcome, rating, outcome_date, created_at
                FROM decision_outcomes
                WHERE decision_id = ANY(%s)
                ORDER BY outcome_date ASC
                """,
                (decision_ids,),
            )
            outcome_rows = cur.fetchall()

    outcomes_by_decision: dict[int, list[OutcomeResponse]] = {}
    for o in outcome_rows:
        resp = OutcomeResponse(
            id=o[0], decision_id=o[1], actual_outcome=o[2],
            rating=o[3], outcome_date=str(o[4]), created_at=str(o[5]),
        )
        outcomes_by_decision.setdefault(o[1], []).append(resp)

    decisions = [
        DecisionWithOutcomes(
            id=r[0], decision_text=r[1], context=r[2], expected_outcome=r[3],
            area=r[4], confidence=float(r[5]), decided_at=str(r[6]), created_at=str(r[7]),
            outcomes=outcomes_by_decision.get(r[0], []),
        )
        for r in decision_rows
    ]

    latency_ms = int((time.time() - started_at) * 1000)
    return DecisionsListResponse(
        decisions=decisions,
        meta={"count": len(decisions), "area": area, "latency_ms": latency_ms},
    )


@router.get("/decisions/patterns", response_model=PatternsResponse)
def analyze_patterns() -> PatternsResponse:
    started_at = time.time()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    d.id, d.decision_text, d.context, d.expected_outcome,
                    d.area, d.confidence, d.decided_at,
                    o.actual_outcome, o.rating, o.outcome_date
                FROM decisions d
                JOIN decision_outcomes o ON o.decision_id = d.id
                ORDER BY d.area, d.decided_at
                """
            )
            rows = cur.fetchall()

    if not rows:
        return PatternsResponse(
            insights="Brak decyzji z zarejestrowanymi wynikami — nie mogę jeszcze wygenerować wzorców.",
            meta={"decision_count": 0, "latency_ms": int((time.time() - started_at) * 1000)},
        )

    grouped: dict[str, list[dict]] = {}
    for r in rows:
        entry = {
            "decision_id": r[0],
            "decision": r[1],
            "context": r[2],
            "expected_outcome": r[3],
            "confidence": float(r[5]),
            "decided_at": str(r[6]),
            "actual_outcome": r[7],
            "rating": r[8],
            "outcome_date": str(r[9]),
        }
        grouped.setdefault(r[4], []).append(entry)

    summary_parts: list[str] = []
    total_decisions = 0
    for area, entries in grouped.items():
        total_decisions += len(entries)
        summary_parts.append(f"## Obszar: {area} ({len(entries)} decyzji)")
        for e in entries:
            summary_parts.append(
                f"- Decyzja: {e['decision']} | Kontekst: {e['context'] or 'brak'} "
                f"| Oczekiwany wynik: {e['expected_outcome'] or 'brak'} "
                f"| Pewność: {e['confidence']:.0%} | Data: {e['decided_at']}\n"
                f"  Faktyczny wynik: {e['actual_outcome']} | Ocena: {e['rating']}/5 | Data wyniku: {e['outcome_date']}"
            )
        summary_parts.append("")

    prompt_data = "\n".join(summary_parts)

    client = Anthropic()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": (
                    "Jesteś osobistym doradcą analitycznym. Przeanalizuj poniższy dziennik decyzji "
                    "i podaj wnioski w języku polskim.\n\n"
                    "Szukaj wzorców takich jak:\n"
                    "- Trafność decyzji w poszczególnych obszarach\n"
                    "- Decyzje podejmowane pod presją vs. przemyślane\n"
                    "- Korelacja pewności siebie z faktycznymi wynikami\n"
                    "- Obszary wymagające poprawy\n"
                    "- Powtarzające się błędy\n\n"
                    "Dane:\n\n"
                    f"{prompt_data}\n\n"
                    "Odpowiedź sformatuj czytelnie z nagłówkami i konkretnymi wnioskami."
                ),
            }
        ],
    )

    from app.db.cost_tracker import log_anthropic_cost
    if hasattr(response, "usage"):
        log_anthropic_cost(ANTHROPIC_MODEL, "api.decisions", response.usage)

    insights = response.content[0].text
    latency_ms = int((time.time() - started_at) * 1000)

    return PatternsResponse(
        insights=insights,
        meta={"decision_count": total_decisions, "areas": list(grouped.keys()), "latency_ms": latency_ms},
    )
