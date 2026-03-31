"""AI-powered report synthesis via Claude Haiku.

Two modes:
- development: emphasis on growth, potential, strengths
- performance: emphasis on delivery, results, expectations

System prompts in Polish. Returns structured JSON.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from .config import ANTHROPIC_MAX_TOKENS, ANTHROPIC_MODEL, MODE_DEVELOPMENT
from .models import CompetencyScore, NineBoxPosition

log = structlog.get_logger("employee_evaluator.ai_synthesizer")

SYSTEM_PROMPT_DEVELOPMENT = """Jesteś ekspertem HR generującym raporty rozwojowe pracowników.
Twoje raporty koncentrują się na:
- Mocnych stronach i potencjale pracownika
- Obszarach do rozwoju z konkretnymi sugestiami
- Budowaniu zaangażowania i motywacji

Pisz profesjonalnym, ale ciepłym językiem HR. Unikaj negatywnego tonu.
Każda obserwacja MUSI być poparta konkretnymi danymi z evidence.

WAŻNE: To jest wstępna ocena wymagająca weryfikacji przez menedżera.
Nie wyciągaj pochopnych wniosków z niepełnych danych.

Odpowiedz WYŁĄCZNIE w formacie JSON:
{
  "executive_summary": "2-3 zdania podsumowania",
  "narrative_strengths": "Opis mocnych stron (2-4 akapity)",
  "narrative_development": "Opis obszarów do rozwoju (2-4 akapity)",
  "key_strengths": ["siła 1", "siła 2", "siła 3"],
  "development_areas": ["obszar 1", "obszar 2"],
  "suggested_actions": ["akcja 1", "akcja 2", "akcja 3"]
}"""

SYSTEM_PROMPT_PERFORMANCE = """Jesteś ekspertem HR generującym raporty oceny wyników pracowników.
Twoje raporty koncentrują się na:
- Realizacji celów i wyników
- Porównaniu z oczekiwaniami na danym stanowisku
- Konkretnych metrykach i trendach

Pisz profesjonalnym, obiektywnym językiem HR. Bazuj na danych, nie opiniach.
Każda obserwacja MUSI być poparta konkretnymi danymi z evidence.

WAŻNE: To jest wstępna ocena wymagająca weryfikacji przez menedżera.
Dane mogą być niepełne — zaznacz to wyraźnie.

Odpowiedz WYŁĄCZNIE w formacie JSON:
{
  "executive_summary": "2-3 zdania podsumowania wyników",
  "narrative_strengths": "Opis osiągnięć i mocnych stron (2-4 akapity)",
  "narrative_development": "Opis wyzwań i obszarów poprawy (2-4 akapity)",
  "key_strengths": ["siła 1", "siła 2", "siła 3"],
  "development_areas": ["obszar 1", "obszar 2"],
  "suggested_actions": ["akcja 1", "akcja 2", "akcja 3"]
}"""


def synthesize_report(
    display_name: str,
    competency_scores: list[CompetencyScore],
    relationship_data: dict[str, Any],
    nine_box: NineBoxPosition | None,
    evaluation_mode: str = MODE_DEVELOPMENT,
    data_completeness: float = 0.0,
) -> dict[str, Any] | None:
    """Generate AI narrative report from evaluation data.

    Returns parsed JSON dict or None on failure.
    """
    try:
        import anthropic
        from app.db.cost_tracker import log_anthropic_cost
    except ImportError:
        log.error("anthropic_sdk_not_available")
        return None

    system_prompt = (
        SYSTEM_PROMPT_DEVELOPMENT
        if evaluation_mode == MODE_DEVELOPMENT
        else SYSTEM_PROMPT_PERFORMANCE
    )

    user_prompt = _build_user_prompt(
        display_name, competency_scores, relationship_data,
        nine_box, data_completeness,
    )

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        log_anthropic_cost(ANTHROPIC_MODEL, "employee_evaluator", response.usage)

        raw_text = response.content[0].text.strip()
        # Extract JSON from response
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        report = json.loads(raw_text)

        log.info(
            "ai_report_generated",
            name=display_name,
            mode=evaluation_mode,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
        )
        return report

    except json.JSONDecodeError as e:
        log.error("ai_report_json_parse_failed", error=str(e))
        return None
    except Exception as e:
        log.error("ai_report_generation_failed", error=str(e), error_type=type(e).__name__)
        return None


def _build_user_prompt(
    display_name: str,
    competency_scores: list[CompetencyScore],
    relationship_data: dict[str, Any],
    nine_box: NineBoxPosition | None,
    data_completeness: float,
) -> str:
    """Build the user prompt with all evaluation data."""
    lines = [
        f"# Ocena pracownika: {display_name}",
        f"Kompletność danych: {data_completeness:.0%}",
        "",
        "## Wyniki kompetencji:",
    ]

    for cs in competency_scores:
        score_str = f"{cs.score:.1f}" if cs.score is not None else "brak danych"
        conf_str = f"{cs.confidence:.0%}"
        lines.append(f"- **{cs.name}**: {score_str} (pewność: {conf_str})")
        if cs.evidence:
            for k, v in cs.evidence.items():
                if k != "reason":
                    lines.append(f"  - {k}: {v}")

    lines.append("")
    lines.append("## Relacje:")
    lines.append(f"- Średnia jakość relacji: {relationship_data.get('avg_health', 0):.2f}")
    lines.append(f"- Rosnące: {relationship_data.get('growing_count', 0)}")
    lines.append(f"- Słabnące: {relationship_data.get('cooling_count', 0)}")
    lines.append(f"- Łącznie relacji: {relationship_data.get('total_relationships', 0)}")

    if nine_box:
        lines.append("")
        lines.append(f"## Pozycja 9-box: {nine_box.label}")
        lines.append(f"- Wyniki: {nine_box.performance_level}")
        lines.append(f"- Potencjał: {nine_box.potential_level}")

    top_rels = relationship_data.get("top_relationships", [])
    if top_rels:
        lines.append("")
        lines.append("## Najsilniejsze relacje:")
        for r in top_rels[:3]:
            lines.append(f"- {r['name']}: health={r.get('health', '?')}, trend={r.get('direction', '?')}")

    return "\n".join(lines)
