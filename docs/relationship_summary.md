# Relationship Module — Summary

**Data: 2026-03-30**
**Status: DEPLOYED (prywatnie)**

> **UWAGA: Ten moduł jest PRYWATNY. NIE montować w main.py ani Omnius routerze.**

## Schema (5 tabel rel_*)

| Tabela | Opis | Wiersze startowe |
|--------|------|-----------------|
| `rel_partners` | Profil partnera | 1 (Natalka) |
| `rel_events` | Zdarzenia w relacji | 0 |
| `rel_patterns` | Wzorce do monitorowania | 5 |
| `rel_journal` | Notatki/journal | 3 |
| `rel_metrics` | Metryki tygodniowe | 1 |

## Moduły (6)

| Moduł | Opis |
|-------|------|
| `partner_profile.py` | CRUD profilu partnera |
| `event_tracker.py` | Logowanie zdarzeń, statystyki sentymentu |
| `pattern_detector.py` | Wzorce, alerty, detekcja |
| `health_scorer.py` | Gottman-inspired scoring 1-10 |
| `coach.py` | Tygodniowe rekomendacje |
| `wa_analyzer.py` | Analiza eksportu WhatsApp |

## Endpointy (13 routes)

```
GET  /relationship/dashboard              — tygodniowy dashboard
GET  /relationship/health-score           — health score 1-10
GET  /relationship/coach                  — rekomendacje
POST /relationship/event                  — log zdarzenia
GET  /relationship/events                 — lista zdarzeń
GET  /relationship/patterns               — aktywne wzorce
POST /relationship/patterns/{id}/seen     — oznacz wzorzec
POST /relationship/journal                — nowa notatka
GET  /relationship/journal                — wpisy z journala
POST /relationship/metrics                — metryki tygodniowe
GET  /relationship/partner                — profil partnera
PATCH /relationship/partner/{id}          — aktualizuj profil
POST /relationship/analyze-chat           — analiza WA eksportu
```

## Jak aktywować

W pliku uruchamiającym serwer (NIE w main.py):

```python
from app.api.relationship import router as rel_router
app.include_router(rel_router, prefix="/relationship", tags=["private"])
```

## Przykładowy dashboard output

```json
{
  "partner": "Natalka Jastrzębska",
  "health_score": 8.4,
  "health_components": {
    "positivity_ratio": {"score": 5.0, "ratio": 0},
    "four_horsemen": {"score": 10.0, "conflicts": 0},
    "initiative_balance": {"score": 6.5, "balance": 0.3},
    "communication_quality": {"score": 8.0},
    "emotional_safety": {"score": 8.0}
  },
  "positivity_ratio": 0.0,
  "events_count": 0,
  "recent_events": [],
  "active_patterns": 5,
  "alerts": [],
  "period_days": 7
}
```

## Wzorce startowe

1. **Fait accompli** (warning) — Sebastian decyduje bez pytania
2. **Initiative check** (reminder) — kto inicjuje rozmowę
3. **Anxious attachment signal** (warning) — "gdzie jest haczyk?"
4. **Non-verbal blindness** (reminder) — pytaj wprost o potrzeby
5. **Communication gap** (warning) — cisza godzinami bez pingu

## Health Score — Gottman Framework

Score 1-10, weighted average:
- Positivity ratio (2.5) — cel 5:1
- Four Horsemen absence (2.0) — -2.5 per konflikt
- Initiative balance (1.5) — 1.0 = ideał
- Communication quality (2.0) — z metryk
- Emotional safety (2.0) — z metryk
- Penalty: -0.5 per aktywny alert

## Bezpieczeństwo

- Router NIE zamontowany w main.py
- Brak structlog dla wrażliwych treści (imion, opisów) — tylko metryki
- Tabele rel_* izolowane
- Komentarz ostrzegawczy w nagłówku app/api/relationship.py
