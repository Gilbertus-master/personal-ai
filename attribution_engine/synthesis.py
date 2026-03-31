"""AI narrative synthesis for attribution results and CEO weekly reports.

Uses Claude Haiku for per-process narratives and Claude Sonnet for
executive-level weekly reports.
"""

from __future__ import annotations

import json

import structlog
from anthropic import Anthropic
from psycopg import Connection

from app.db.cost_tracker import log_anthropic_cost

from .models import AttributionResult

log = structlog.get_logger("attribution_engine.synthesis")

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-5"
MAX_TOKENS_NARRATIVE = 800
MAX_TOKENS_REPORT = 2000

_client = Anthropic()

ATTRIBUTION_SYSTEM_PROMPT = """\
Jestes analitykiem organizacyjnym dla CEO holdingu energetycznego.
Analizujesz przyczyny problemow/sukcesow w procesach firmowych.

Na podstawie danych atrybucji wygeneruj JSON z polami:
- "narrative": 2-3 zdania wyjasniajace PRZYCZYNE anomalii (ton rzeczowy, konkretne dane)
- "primary_recommendation": 1 zdanie z rekomendacja dzialania
- "recommendation_type": jeden z: 'process_fix', 'people_intervention', 'team_restructure', 'monitoring', 'external_response'
- "caveat": 1 zdanie o ograniczeniach analizy

Uzywaj danych liczbowych. Nie wymyslaj danych. Odpowiedz WYLACZNIE poprawnym JSON-em.
"""

CEO_REPORT_SYSTEM_PROMPT = """\
Jestes doradca strategicznym CEO holdingu energetycznego (Respect Energy Holding).
Przygotowujesz tygodniowy raport o zdrowiu organizacji.

Na podstawie danych wygeneruj JSON z polami:
- "headline": 1 zdanie — najwazniejszy insight tygodnia (max 120 znakow)
- "financial_insight": 2-3 zdania o sytuacji finansowej procesow
- "people_risk_insight": 2-3 zdania o ryzykach personalnych
- "process_insight": 2-3 zdania o stanie procesow
- "top_3_actions": lista 3 priorytetowych akcji CEO (kazda: {"action": str, "urgency": "immediate"|"this_week"|"next_week", "impact": str})
- "positive_highlights": lista 1-3 pozytywnych sygnalow

Ton: zwiezly, rzeczowy, bez emocji. Uzywaj konkretnych liczb i nazw.
Odpowiedz WYLACZNIE poprawnym JSON-em.
"""


def _build_attribution_payload(attribution: AttributionResult, process_name: str) -> str:
    """Build a concise payload for the attribution narrative prompt."""
    payload = {
        "process": process_name,
        "kierunek": attribution.direction,
        "severity": attribution.severity,
        "atrybucja": {
            "proces": attribution.attribution_process,
            "ludzie": attribution.attribution_people,
            "interakcje": attribution.attribution_interaction,
            "zewnetrzne": attribution.attribution_external,
            "nieznane": attribution.attribution_unknown,
        },
        "confidence": attribution.confidence,
        "tygodnie_danych": attribution.min_weeks_data,
        "anomalie": attribution.interaction_signals.get("anomalies", [])[:5],
        "sredni_flight_risk": attribution.people_signals.get("avg_flight_risk", 0),
        "srednia_delivery": attribution.people_signals.get("avg_delivery_score", 0),
        "health_trend": attribution.process_signals.get("health_trend", [])[-4:],
        "top_negatywni": attribution.top_people_negative[:3],
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def generate_attribution_narrative(
    attribution: AttributionResult,
    conn: Connection,
) -> dict:
    """Generate AI narrative for a single attribution result.

    Calls Claude Haiku with Polish system prompt.

    Returns:
        Dict with keys: narrative, primary_recommendation, recommendation_type, caveat.
    """
    # Get process name
    process_name = "Unknown"
    with conn.cursor() as cur:
        cur.execute(
            "SELECT process_name FROM processes WHERE process_id = %s",
            (str(attribution.process_id),),
        )
        row = cur.fetchone()
        if row:
            process_name = row[0]

    payload = _build_attribution_payload(attribution, process_name)

    log.info(
        "generating_narrative",
        process_id=str(attribution.process_id),
        model=HAIKU_MODEL,
    )

    try:
        response = _client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=MAX_TOKENS_NARRATIVE,
            system=ATTRIBUTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": payload}],
        )
        log_anthropic_cost(HAIKU_MODEL, "attribution_engine.narrative", response.usage)

        raw_text = response.content[0].text.strip()
        result = json.loads(raw_text)

        log.info("narrative_generated", process=process_name)
        return {
            "narrative": result.get("narrative", ""),
            "primary_recommendation": result.get("primary_recommendation", ""),
            "recommendation_type": result.get("recommendation_type", "monitoring"),
            "caveat": result.get("caveat", ""),
        }

    except json.JSONDecodeError as exc:
        log.error("narrative_json_parse_error", error=str(exc))
        return {
            "narrative": raw_text if "raw_text" in dir() else "",
            "primary_recommendation": "",
            "recommendation_type": "monitoring",
            "caveat": "Blad parsowania odpowiedzi AI.",
        }
    except Exception as exc:
        log.error("narrative_generation_failed", error=str(exc))
        return {
            "narrative": "",
            "primary_recommendation": "",
            "recommendation_type": "monitoring",
            "caveat": f"Blad generowania narracji: {exc}",
        }


def generate_ceo_weekly_report(
    snapshot: dict,
    conn: Connection,
) -> dict:
    """Generate executive weekly report using Claude Sonnet.

    Args:
        snapshot: Dict with org health snapshot data.
        conn: DB connection (for additional context if needed).

    Returns:
        Dict with keys: headline, financial_insight, people_risk_insight,
        process_insight, top_3_actions, positive_highlights.
    """
    payload = json.dumps(snapshot, ensure_ascii=False, default=str)

    log.info("generating_ceo_report", model=SONNET_MODEL)

    try:
        response = _client.messages.create(
            model=SONNET_MODEL,
            max_tokens=MAX_TOKENS_REPORT,
            system=CEO_REPORT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": payload}],
        )
        log_anthropic_cost(SONNET_MODEL, "attribution_engine.ceo_report", response.usage)

        raw_text = response.content[0].text.strip()
        result = json.loads(raw_text)

        log.info("ceo_report_generated")
        return {
            "headline": result.get("headline", ""),
            "financial_insight": result.get("financial_insight", ""),
            "people_risk_insight": result.get("people_risk_insight", ""),
            "process_insight": result.get("process_insight", ""),
            "top_3_actions": result.get("top_3_actions", []),
            "positive_highlights": result.get("positive_highlights", []),
        }

    except json.JSONDecodeError as exc:
        log.error("ceo_report_json_parse_error", error=str(exc))
        return {
            "headline": "Blad generowania raportu",
            "financial_insight": "",
            "people_risk_insight": "",
            "process_insight": "",
            "top_3_actions": [],
            "positive_highlights": [],
        }
    except Exception as exc:
        log.error("ceo_report_generation_failed", error=str(exc))
        return {
            "headline": f"Blad: {exc}",
            "financial_insight": "",
            "people_risk_insight": "",
            "process_insight": "",
            "top_3_actions": [],
            "positive_highlights": [],
        }
