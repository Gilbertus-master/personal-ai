# PRIVATE — nie eksponować w Omnius ani publicznym API
#
# Relationship Coach — tygodniowe rekomendacje dla Sebastiana
# Bazuje na: health score, patterns, events, profilu Sebastiana (F84.5 Asperger)
from __future__ import annotations

from datetime import datetime

import structlog

from app.analysis.relationship.health_scorer import compute_health_score
from app.analysis.relationship.pattern_detector import get_active_patterns, get_alerts
from app.analysis.relationship.event_tracker import get_sentiment_stats
from app.config.timezone import APP_TIMEZONE as CET

log = structlog.get_logger("rel.coach")

# Sebastian's profile context for coaching
SEBASTIAN_CONTEXT = {
    "diagnosis": "F84.5 Asperger",
    "blind_spots": [
        "nie czyta sygnałów niewerbalnych",
        "podejmuje decyzje sam (fait accompli)",
        "krótkie odpowiedzi mogą być odebrane jako brak zainteresowania",
    ],
    "strengths": [
        "analityczny — potrafi zrozumieć wzorce po wyjaśnieniu",
        "lojalny i zaangażowany gdy decyduje się na relację",
        "acts of service — pokazuje troskę przez działanie",
    ],
    "love_style": "acts of service + words of affirmation",
}


def generate_recommendations(partner_id: int = 1) -> dict:
    """Generuj tygodniowe rekomendacje dla relacji."""
    health = compute_health_score(partner_id)
    patterns = get_active_patterns(partner_id)
    alerts = get_alerts(partner_id)
    stats = get_sentiment_stats(partner_id, days=7)

    recommendations = []

    # --- Health-score based ---
    score = health["health_score"]
    if score < 5:
        recommendations.append({
            "priority": "high",
            "area": "health",
            "action": "Health score niski. Zaplanuj dedicated quality time z Natalką w tym tygodniu.",
            "why": "Score poniżej 5 oznacza kumulację problemów.",
        })
    elif score < 7:
        recommendations.append({
            "priority": "medium",
            "area": "health",
            "action": "Health score umiarkowany. Sprawdź co obniża score i adresuj najsłabszy komponent.",
            "why": f"Najsłabszy obszar: {_weakest_component(health)}",
        })

    # --- Positivity ratio ---
    ratio = stats["positivity_ratio"]
    if ratio < 3.0:
        recommendations.append({
            "priority": "high",
            "area": "positivity",
            "action": f"Positivity ratio: {ratio}:1 (cel: 5:1). Dodaj więcej pozytywnych interakcji: komplement, wdzięczność, wspólna aktywność.",
            "why": "Gottman: relacje poniżej 5:1 są w strefie ryzyka.",
        })

    # --- Initiative balance ---
    ib = health["components"]["initiative_balance"]["balance"]
    if ib is not None and ib < 0.6:
        recommendations.append({
            "priority": "high",
            "area": "initiative",
            "action": "Za mało Twoich inicjatyw. Jutro PIERWSZY napisz do Natalki rano. Zapytaj jak się czuje.",
            "why": "Natalka inicjuje większość rozmów. Asperger: świadomie kompensuj.",
        })

    # --- Pattern-based ---
    for p in patterns:
        if p["occurrences"] >= p["alert_threshold"]:
            recommendations.append({
                "priority": "high",
                "area": "pattern",
                "action": f"Wzorzec '{p['pattern_name']}' aktywny ({p['occurrences']}x). {p.get('detection_hint', '')}",
                "why": p["description"],
            })

    # --- Asperger-specific reminders ---
    recommendations.append({
        "priority": "medium",
        "area": "asperger",
        "action": "Pytaj Natalkę wprost: 'Jak się czujesz?', 'Czego teraz potrzebujesz?'. Nie zakładaj że wiesz.",
        "why": "F84.5: nie czytasz sygnałów niewerbalnych. Explicit > implicit.",
    })

    # --- Weekly check ---
    if stats["total"] < 3:
        recommendations.append({
            "priority": "medium",
            "area": "tracking",
            "action": "Mało zdarzeń zalogowanych w tym tygodniu. Loguj ważne momenty — pozytywne i negatywne.",
            "why": "Bez danych system nie może dobrze ocenić zdrowia relacji.",
        })

    # --- Sort by priority ---
    priority_order = {"high": 0, "medium": 1, "low": 2}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 99))

    result = {
        "health_score": score,
        "recommendations": recommendations,
        "stats": {
            "events_7d": stats["total"],
            "positivity_ratio": ratio,
            "active_alerts": len(alerts),
        },
        "generated_at": str(datetime.now(CET)),
    }

    log.info("rel.coach.generated", recommendations=len(recommendations), score=score)
    return result


def _weakest_component(health: dict) -> str:
    """Znajdź najsłabszy komponent health score."""
    components = health.get("components", {})
    if not components:
        return "unknown"
    weakest = min(components.items(), key=lambda x: x[1].get("score", 10))
    return f"{weakest[0]} ({weakest[1]['score']}/10)"
