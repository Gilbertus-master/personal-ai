"""
AI-powered employee evaluator using Claude.

Takes collected person data and generates structured evaluation:
- WHAT (achievements, goals met)
- HOW (work style, communication, initiative)
- WEAK POINTS (failures, areas for improvement)
- Quantified scores (1-5 per dimension)
- Confidence score based on data volume
"""
from __future__ import annotations

import json
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

EVAL_SYSTEM_PROMPT = """
Jesteś ekspertem HR i analitykiem organizacyjnym. Na podstawie dostarczonych danych
(wydarzenia, fragmenty komunikacji, statystyki) przygotuj szczegółową ocenę pracownika.

Ocena MUSI zawierać dokładnie te sekcje w formacie JSON:

{
  "what": {
    "summary": "Opis osiągnięć i zrealizowanych celów (3-5 zdań)",
    "achievements": ["lista konkretnych osiągnięć z datami i liczbami"],
    "goals_met": ["zrealizowane cele"],
    "goals_missed": ["niezrealizowane cele, jeśli widoczne w danych"]
  },
  "how": {
    "summary": "Opis stylu pracy, komunikacji, inicjatywy (3-5 zdań)",
    "strengths": ["mocne strony widoczne w danych"],
    "work_style": "reaktywny/proaktywny/mieszany"
  },
  "weak_points": {
    "summary": "Opis słabych stron i porażek (3-5 zdań)",
    "failures": ["konkretne porażki/błędy z datami"],
    "improvement_areas": ["obszary wymagające poprawy"]
  },
  "scores": {
    "goal_achievement": {"score": 1-5, "comment": "uzasadnienie"},
    "initiative": {"score": 1-5, "comment": "uzasadnienie"},
    "quality": {"score": 1-5, "comment": "uzasadnienie"},
    "communication": {"score": 1-5, "comment": "uzasadnienie"},
    "team_management": {"score": 1-5, "comment": "uzasadnienie"},
    "risk_management": {"score": 1-5, "comment": "uzasadnienie"}
  },
  "overall_score": 1.0-5.0,
  "bonus_recommendation": "XX-YY% premii docelowej",
  "retention_priority": "KRYTYCZNY/BARDZO WYSOKI/WYSOKI/ŚREDNI/NISKI"
}

Zasady:
- Opieraj się WYŁĄCZNIE na dostarczonych danych. Nie zmyślaj.
- Bądź konkretny — nazwiska, daty, kwoty, procenty.
- Oceniaj uczciwie — nie zawyżaj ani nie zaniżaj.
- Wyraźnie zaznacz porażki i słabe strony.
- Jeśli danych jest mało, obniż confidence i zaznacz to.
- Odpowiedz TYLKO JSON, bez dodatkowego tekstu.
"""

EVAL_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "evaluation": {
            "type": "object",
            "properties": {
                "what": {"type": "object"},
                "how": {"type": "object"},
                "weak_points": {"type": "object"},
                "scores": {"type": "object"},
                "overall_score": {"type": "number"},
                "bonus_recommendation": {"type": "string"},
                "retention_priority": {"type": "string"},
            },
            "required": ["what", "how", "weak_points", "scores", "overall_score",
                         "bonus_recommendation", "retention_priority"],
        }
    },
    "required": ["evaluation"],
}


def evaluate_person(person_data: dict[str, Any]) -> dict[str, Any]:
    """Generate evaluation from collected person data."""

    person = person_data["person"]
    stats = person_data["stats"]
    events = person_data["events"]
    chunks = person_data["chunks"]
    period = person_data["period"]

    # Build context for Claude
    context_parts = [
        f"Oceniany: {person['name']}",
        f"Stanowisko: {person.get('role', '?')}",
        f"Organizacja: {person.get('organization', '?')}",
        f"Okres oceny: {period.get('from', '?')} — {period.get('to', '?')}",
        f"Sentiment relacji: {person.get('sentiment', '?')}",
        "",
        f"STATYSTYKI: {stats['total_events']} wydarzeń, {stats['total_chunks']} wzmianek",
        f"Podział wydarzeń: {json.dumps(stats['event_type_breakdown'], ensure_ascii=False)}",
        f"Aktywność miesięczna: {json.dumps(stats['monthly_activity'], ensure_ascii=False)}",
        "",
        "=== WYDARZENIA (chronologicznie) ===",
    ]

    for ev in events[:300]:
        context_parts.append(f"[{ev['type']}] {ev['time'] or '?'}: {ev['summary']}")

    context_parts.append("")
    context_parts.append("=== FRAGMENTY KOMUNIKACJI (najnowsze) ===")
    for ch in chunks[:100]:
        context_parts.append(f"[{ch['source']}] {ch['date'] or '?'}: {ch['text'][:300]}")

    if person_data.get("open_loops"):
        context_parts.append("")
        context_parts.append("=== OTWARTE SPRAWY ===")
        for ol in person_data["open_loops"]:
            context_parts.append(f"- {ol['description']}")

    context = "\n".join(context_parts)

    # Truncate to ~80k chars (leaving room for system prompt)
    if len(context) > 80000:
        context = context[:80000] + "\n\n[...truncated...]"

    # Call Claude
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4000,
        temperature=0.1,
        system=[{"type": "text", "text": EVAL_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": context}],
        tools=[{
            "name": "return_evaluation",
            "description": "Return the structured employee evaluation",
            "input_schema": EVAL_TOOL_SCHEMA,
        }],
        tool_choice={"type": "tool", "name": "return_evaluation"},
    )

    if hasattr(response, "usage"):
        log_anthropic_cost(ANTHROPIC_MODEL, "evaluation.evaluator", response.usage)

    # Extract evaluation
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            eval_data = block.input.get("evaluation", block.input)

            # Calculate confidence based on data volume
            data_score = min(stats["total_events"] / 50, 1.0) * 0.5 + min(stats["total_chunks"] / 100, 1.0) * 0.5
            confidence = round(min(data_score, 0.85), 2)  # Cap at 0.85 (single-perspective limit)

            return {
                "person": person,
                "period": period,
                "evaluation": eval_data,
                "confidence": confidence,
                "confidence_note": (
                    "Ocena oparta na danych z perspektywy board member (Teams/email SJ). "
                    "Brak danych z perspektywy ocenianego pracownika."
                    if confidence < 0.9 else "Ocena wieloperspektywiczna."
                ),
                "data_volume": {
                    "events": stats["total_events"],
                    "chunks": stats["total_chunks"],
                },
            }

    return {"error": "Evaluation generation failed — no structured output returned"}
