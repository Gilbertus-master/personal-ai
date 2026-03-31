"""Maturity survey: 5-question PML assessment for processes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

log = structlog.get_logger("process_evaluator.maturity_survey")

# PML survey questions (1-5 scale each)
_SURVEY_QUESTIONS = [
    {
        "id": 1,
        "question": "Czy proces jest udokumentowany i posiada aktualną instrukcję?",
        "description": "1=Brak dokumentacji, 5=Pełna, aktualna dokumentacja z diagramami",
        "dimension": "documentation",
    },
    {
        "id": 2,
        "question": "Czy proces jest powtarzalny — ten sam input daje ten sam output?",
        "description": "1=Każde wykonanie jest inne, 5=W pełni standaryzowany i powtarzalny",
        "dimension": "repeatability",
    },
    {
        "id": 3,
        "question": "Czy proces ma zdefiniowane metryki i są regularnie mierzone?",
        "description": "1=Brak metryk, 5=Dashboard z alertami i trendami",
        "dimension": "measurability",
    },
    {
        "id": 4,
        "question": "Czy proces jest zarządzany — są właściciele, review cykliczne?",
        "description": "1=Nikt nie odpowiada, 5=Owner + regularne przeglądy + SLA",
        "dimension": "governance",
    },
    {
        "id": 5,
        "question": "Czy proces jest aktywnie optymalizowany — czy była zmiana w ostatnim kwartale?",
        "description": "1=Nikt nie dotykał od lat, 5=Ciągłe udoskonalanie, A/B testy",
        "dimension": "optimization",
    },
]


def get_survey_questions() -> list[dict[str, Any]]:
    """Return the 5 PML survey questions."""
    return [dict(q) for q in _SURVEY_QUESTIONS]


def record_survey_response(
    process_id: UUID,
    responses: list[int],
    conn: psycopg.Connection,
) -> dict[str, Any]:
    """Record maturity survey responses and update PML level.

    Args:
        process_id: Process UUID.
        responses: List of 5 integers (1-5 each).
        conn: Database connection.

    Returns:
        dict with pml_level, avg_score, survey_date.
    """
    if len(responses) != 5:
        raise ValueError(f"Expected 5 responses, got {len(responses)}")
    for i, r in enumerate(responses):
        if not (1 <= r <= 5):
            raise ValueError(f"Response {i+1} must be 1-5, got {r}")

    avg_score = sum(responses) / len(responses)
    pml_level = max(1, min(5, round(avg_score)))
    survey_date = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        # UPSERT: update existing or insert new record
        cur.execute(
            """INSERT INTO process_competency_scores (process_id, process_maturity_level, maturity_survey_date,
                   score_maturity, maturity_evidence, maturity_confidence)
               VALUES (%s, %s, %s, %s, %s, 0.9)
               ON CONFLICT (process_id, cycle_id)
               DO UPDATE SET
                   process_maturity_level = EXCLUDED.process_maturity_level,
                   maturity_survey_date = EXCLUDED.maturity_survey_date,
                   score_maturity = EXCLUDED.score_maturity,
                   maturity_evidence = EXCLUDED.maturity_evidence,
                   maturity_confidence = EXCLUDED.maturity_confidence""",
            (
                str(process_id),
                pml_level,
                survey_date,
                float(pml_level),  # Direct 1-5 mapping
                _build_survey_evidence(responses, avg_score),
            ),
        )
    conn.commit()

    log.info(
        "maturity_survey_recorded",
        process_id=str(process_id),
        pml_level=pml_level,
        avg_score=round(avg_score, 2),
    )

    return {
        "process_id": str(process_id),
        "pml_level": pml_level,
        "avg_score": round(avg_score, 2),
        "survey_date": survey_date.isoformat(),
        "responses": dict(zip(
            [q["dimension"] for q in _SURVEY_QUESTIONS],
            responses,
        )),
    }


def get_pending_surveys(conn: psycopg.Connection) -> list[dict[str, Any]]:
    """Get processes needing a maturity survey (no survey in last 90 days).

    Returns list of dicts with process_id, process_name, last_survey_date.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT p.process_id, p.process_name, p.process_type,
                      MAX(pcs.maturity_survey_date) AS last_survey_date
               FROM processes p
               LEFT JOIN process_competency_scores pcs
                   ON pcs.process_id = p.process_id
                   AND pcs.maturity_survey_date IS NOT NULL
               WHERE p.status = 'active'
               GROUP BY p.process_id, p.process_name, p.process_type
               HAVING MAX(pcs.maturity_survey_date) IS NULL
                   OR MAX(pcs.maturity_survey_date) < %s
               ORDER BY MAX(pcs.maturity_survey_date) ASC NULLS FIRST""",
            (cutoff,),
        )
        rows = cur.fetchall()

    results = []
    for row in rows:
        results.append({
            "process_id": str(row["process_id"]),
            "process_name": row["process_name"],
            "process_type": row["process_type"],
            "last_survey_date": str(row["last_survey_date"]) if row["last_survey_date"] else None,
            "days_since_survey": (
                (datetime.now(timezone.utc) - row["last_survey_date"]).days
                if row["last_survey_date"]
                else None
            ),
        })

    return results


def _build_survey_evidence(responses: list[int], avg_score: float) -> str:
    """Build JSONB evidence string from survey responses."""
    import json
    evidence = {
        "source": "survey",
        "avg_score": round(avg_score, 2),
        "responses": {},
    }
    for q, r in zip(_SURVEY_QUESTIONS, responses):
        evidence["responses"][q["dimension"]] = r
    return json.dumps(evidence, ensure_ascii=False)
