"""AI-powered process narrative synthesis via Claude Haiku.

Generates Polish-language analysis: narrative, key findings, recommendations.
"""

from __future__ import annotations

import json
import os
from typing import Any

import structlog

from .models import DimensionScore

log = structlog.get_logger("process_evaluator.ai_synthesizer")

ANTHROPIC_MODEL = os.getenv(
    "PE_ANTHROPIC_MODEL",
    os.getenv("ANTHROPIC_EXTRACTION_MODEL", "claude-haiku-4-5-20251001"),
)
ANTHROPIC_MAX_TOKENS = int(os.getenv("PE_ANTHROPIC_MAX_TOKENS", "1500"))

SYSTEM_PROMPT = """Jesteś ekspertem od zarządzania procesami biznesowymi, generujesz raporty zdrowia procesów.
Twoje raporty koncentrują się na:
- Aktualnym stanie zdrowia procesu i kluczowych wskaźnikach
- Największych ryzykach i wąskich gardłach
- Konkretnych rekomendacjach z przypisanym właścicielem

Pisz profesjonalnym, zwięzłym językiem. Bazuj na danych, nie opiniach.
Każda obserwacja MUSI być poparta konkretnymi danymi z evidence.

WAŻNE: To jest wstępna ocena wymagająca weryfikacji przez process ownera.
Dane mogą być niepełne — zaznacz to wyraźnie.

Odpowiedz WYŁĄCZNIE w formacie JSON:
{
  "narrative": "2-3 zdania podsumowania stanu procesu",
  "key_findings": ["finding 1", "finding 2", "finding 3"],
  "recommendations": [
    {"action": "co zrobić", "owner": "kto powinien", "priority": "high|medium|low"},
    {"action": "co zrobić", "owner": "kto powinien", "priority": "high|medium|low"},
    {"action": "co zrobić", "owner": "kto powinien", "priority": "high|medium|low"}
  ]
}"""


def generate_process_narrative(
    process_name: str,
    process_type: str,
    scores_dict: dict[str, DimensionScore],
    health_score: float,
    failure_risk: float,
    box_label: str,
    conn: Any,
) -> dict[str, Any] | None:
    """Generate AI narrative for a process evaluation.

    Returns dict with 'narrative', 'key_findings', 'recommendations' or None on failure.
    """
    try:
        import anthropic
        from app.db.cost_tracker import log_anthropic_cost
    except ImportError:
        log.error("anthropic_sdk_not_available")
        return None

    user_prompt = _build_user_prompt(
        process_name, process_type, scores_dict, health_score, failure_risk, box_label,
    )

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        log_anthropic_cost(ANTHROPIC_MODEL, "process_evaluator", response.usage)

        raw_text = response.content[0].text.strip()
        # Extract JSON from potential markdown code block
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        result = json.loads(raw_text)

        # Normalize recommendations to flat list of strings for storage
        recs_flat = []
        for rec in result.get("recommendations", []):
            if isinstance(rec, dict):
                recs_flat.append(f"[{rec.get('priority', 'medium')}] {rec.get('action', '')} (owner: {rec.get('owner', '?')})")
            else:
                recs_flat.append(str(rec))

        log.info(
            "ai_narrative_generated",
            process=process_name,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
        )

        return {
            "narrative": result.get("narrative", ""),
            "key_findings": result.get("key_findings", []),
            "recommendations": recs_flat,
            "model_used": ANTHROPIC_MODEL,
        }

    except json.JSONDecodeError as e:
        log.error("ai_narrative_json_parse_failed", error=str(e))
        return None
    except Exception as e:
        log.error("ai_narrative_generation_failed", error=str(e), error_type=type(e).__name__)
        return None


def _build_user_prompt(
    process_name: str,
    process_type: str,
    scores_dict: dict[str, DimensionScore],
    health_score: float,
    failure_risk: float,
    box_label: str,
) -> str:
    """Build the user prompt with all evaluation data."""
    lines = [
        f"# Ocena procesu: {process_name}",
        f"Typ procesu: {process_type}",
        f"Wynik zdrowia: {health_score:.1f}/100",
        f"Ryzyko awarii: {failure_risk:.1%}",
        f"Kategoria procesu: {box_label}",
        "",
        "## Wyniki wymiarów (skala 1-5):",
    ]

    dimension_names_pl = {
        "throughput": "Przepustowość",
        "quality": "Jakość",
        "maturity": "Dojrzałość",
        "handoff": "Przekazania",
        "cost": "Koszty",
        "improvement": "Doskonalenie",
        "scalability": "Skalowalność",
        "dependency": "Zależności",
    }

    for dim_key in ("throughput", "quality", "maturity", "handoff",
                     "cost", "improvement", "scalability", "dependency"):
        ds = scores_dict.get(dim_key)
        name_pl = dimension_names_pl.get(dim_key, dim_key)
        if ds and ds.score is not None:
            lines.append(f"- **{name_pl}** (D{list(dimension_names_pl.keys()).index(dim_key)+1}): {ds.score:.1f} (pewność: {ds.confidence:.0%})")
            if ds.evidence:
                for k, v in ds.evidence.items():
                    if k not in ("reason", "source") and not isinstance(v, (dict, list)):
                        lines.append(f"  - {k}: {v}")
        else:
            lines.append(f"- **{name_pl}**: brak danych")

    # Highlight critical dependency info
    dep = scores_dict.get("dependency")
    if dep and dep.evidence:
        lines.append("")
        lines.append("## Kluczowe ryzyka ludzkie:")
        bf = dep.evidence.get("bus_factor")
        kc = dep.evidence.get("knowledge_concentration")
        frw = dep.evidence.get("flight_risk_weighted")
        cpc = dep.evidence.get("critical_person_count", 0)
        if bf is not None:
            lines.append(f"- Bus factor: {bf}")
        if kc is not None:
            lines.append(f"- Koncentracja wiedzy: {kc:.0%}")
        if frw is not None:
            lines.append(f"- Ważony flight risk: {frw:.0%}")
        if cpc > 0:
            lines.append(f"- Krytyczne osoby (high ownership + high flight risk): {cpc}")

    return "\n".join(lines)
