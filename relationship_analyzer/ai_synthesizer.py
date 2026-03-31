"""AI narrative synthesis using Claude Haiku.

Generates a concise relationship narrative in Polish, including strengths,
risks, opportunities, and a recommended next action.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from anthropic import Anthropic

from app.db.cost_tracker import log_anthropic_cost

from .models import AISynthesis

log = structlog.get_logger("relationship_analyzer.ai_synthesizer")

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1000

SYSTEM_PROMPT = """\
Jestes asystentem analizujacym relacje miedzyludzkie dla Sebastiana Jablonskiego, \
CEO holdingu energetycznego. Twoje odpowiedzi sa zwiezle, konkretne i w jezyku polskim.

Na podstawie danych analitycznych wygeneruj JSON z nastepujacymi polami:
- "narrative_summary": 3-5 zdan podsumowujacych relacje (ton rzeczowy, bez emocji)
- "key_strengths": lista 1-3 mocnych stron relacji
- "key_risks": lista 0-3 ryzyk lub sygnalow ostrzegawczych
- "opportunities": lista 0-2 mozliwosci do wykorzystania
- "recommended_action": 1 zdanie z konkretna rekomendacja dzialania

Odpowiedz WYLACZNIE poprawnym JSON-em, bez markdown, bez komentarzy.
Uzywaj danych liczbowych w narracji (np. "kontakt 3x/tydzien", "tie_strength 0.72").
Nie wymyslaj danych ktorych nie ma w inputcie.
"""


def _build_signal_payload(
    name_a: str,
    name_b: str,
    perspectives_dyadic: dict[str, Any],
    health_score: int,
    health_label: str,
) -> str:
    """Build a concise signal payload for the LLM (no raw messages, no PII beyond names)."""
    signals = {
        "osoba_a": name_a,
        "osoba_b": name_b,
        "health_score": health_score,
        "health_label": health_label,
    }

    # Cherry-pick key signals from perspectives
    key_fields = [
        "interaction_count_total", "avg_interactions_per_week",
        "days_since_last_contact", "relationship_duration_days",
        "dominant_channel", "initiation_ratio", "response_rate",
        "lag_asymmetry", "avg_sentiment_ego", "avg_sentiment_alter",
        "emotional_support_score", "conflict_detected",
        "trajectory_status", "tie_strength_current",
        "tie_strength_delta_30d", "lifecycle_stage",
        "top_topics", "shared_entities_count", "discussion_depth_score",
        "shared_contacts_count", "open_loops_count",
        "communication_style_match", "language_accommodation",
    ]
    for field in key_fields:
        val = perspectives_dyadic.get(field)
        if val is not None:
            signals[field] = val

    return json.dumps(signals, ensure_ascii=False, default=str)


def generate_synthesis(
    name_a: str,
    name_b: str,
    perspectives_dyadic: dict[str, Any],
    health_score: int,
    health_label: str,
) -> AISynthesis:
    """Call Claude Haiku to generate narrative synthesis.

    Returns AISynthesis with narrative_summary, key_strengths, key_risks,
    opportunities, recommended_action.
    """
    payload = _build_signal_payload(
        name_a, name_b, perspectives_dyadic, health_score, health_label
    )

    client = Anthropic()

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": payload}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(MODEL, "relationship_analyzer", response.usage)

        raw_text = response.content[0].text.strip()

        # Parse JSON response
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to extract JSON from possible markdown wrapping
            import re
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                log.warning("ai_synthesis_json_parse_failed", raw_text=raw_text[:200])
                return AISynthesis(
                    narrative_summary=raw_text[:500],
                    model_used=MODEL,
                    confidence=0.3,
                )

        synthesis = AISynthesis(
            narrative_summary=data.get("narrative_summary", ""),
            key_strengths=data.get("key_strengths", []),
            key_risks=data.get("key_risks", []),
            opportunities=data.get("opportunities", []),
            recommended_action=data.get("recommended_action", ""),
            model_used=MODEL,
            confidence=0.8,
        )

        log.info(
            "ai_synthesis_generated",
            name_a=name_a,
            name_b=name_b,
            summary_len=len(synthesis.narrative_summary),
        )

        return synthesis

    except Exception:
        log.exception("ai_synthesis_failed", name_a=name_a, name_b=name_b)
        return AISynthesis(model_used=MODEL, confidence=0.0)
