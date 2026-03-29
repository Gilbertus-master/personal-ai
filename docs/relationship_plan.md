# Relationship Module — Plan

**Data: 2026-03-30**

## A. DB Schema (prywatne tabele rel_)

```sql
-- Profil partnera
rel_partners (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    phone VARCHAR(20),
    birth_date DATE,
    birth_time TIME,
    attachment_style VARCHAR(50),
    love_languages TEXT,
    communication_style TEXT,
    needs TEXT,
    boundaries TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Zdarzenia w relacji
rel_events (
    id SERIAL PRIMARY KEY,
    partner_id INTEGER REFERENCES rel_partners(id),
    event_type VARCHAR(50) NOT NULL,  -- date, conflict, milestone, concern, positive, negative, boundary, communication
    title VARCHAR(300),
    description TEXT,
    sentiment NUMERIC(3,1),  -- -5.0 do +5.0
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Wzorce do monitorowania
rel_patterns (
    id SERIAL PRIMARY KEY,
    partner_id INTEGER REFERENCES rel_partners(id),
    pattern_name VARCHAR(200) NOT NULL,
    pattern_type VARCHAR(50) DEFAULT 'warning',  -- warning, reminder, positive
    description TEXT,
    detection_hint TEXT,  -- jak wykryć
    last_seen TIMESTAMPTZ,
    occurrences INTEGER DEFAULT 0,
    alert_threshold INTEGER DEFAULT 3,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Journal relacji
rel_journal (
    id SERIAL PRIMARY KEY,
    partner_id INTEGER REFERENCES rel_partners(id),
    entry TEXT NOT NULL,
    mood INTEGER CHECK (mood BETWEEN 1 AND 10),
    tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Metryki tygodniowe
rel_metrics (
    id SERIAL PRIMARY KEY,
    partner_id INTEGER REFERENCES rel_partners(id),
    week_start DATE NOT NULL,
    communication_quality INTEGER CHECK (communication_quality BETWEEN 1 AND 10),
    positivity_ratio NUMERIC(4,2),  -- Gottman 5:1
    initiative_balance NUMERIC(3,1),  -- 0=tylko partner, 1=równo, 2=tylko Sebastian
    emotional_safety INTEGER CHECK (emotional_safety BETWEEN 1 AND 10),
    vulnerability_level INTEGER CHECK (vulnerability_level BETWEEN 1 AND 10),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(partner_id, week_start)
)
```

## B. Architektura

```
app/analysis/relationship/
  __init__.py
  partner_profile.py   — CRUD profilu partnera
  event_tracker.py     — logowanie zdarzeń, query po typie/dacie
  pattern_detector.py  — wykrywanie wzorców, alerty
  health_scorer.py     — Gottman-inspired scoring (5:1, Four Horsemen)
  coach.py             — tygodniowe rekomendacje, actionable advice
  wa_analyzer.py       — (przyszłość) analiza eksportu WhatsApp

app/api/relationship.py — PRYWATNY router, NIE montować w main.py
```

## C. Endpointy API (prywatne, localhost)

```
GET  /relationship/dashboard              — tygodniowy stan relacji
POST /relationship/event                  — log zdarzenia
GET  /relationship/events?days=7          — ostatnie zdarzenia
GET  /relationship/patterns               — aktywne wzorce
POST /relationship/patterns/{id}/seen     — oznacz pattern jako widziany
POST /relationship/journal                — nowa notatka
GET  /relationship/journal?days=30        — ostatnie wpisy
GET  /relationship/coach                  — tygodniowe rekomendacje
GET  /relationship/health-score           — aktualny health score 1-10
POST /relationship/metrics                — dodaj metryki tygodniowe
```

## D. Dane startowe

### Partner: Natalka Jastrzębska
- Tel: +48 731 066 373
- Attachment: anxious-secure
- Love languages: physical touch, quality time
- Communication: emocjonalna, pyta dużo, inicjuje tematycznie
- Needs: potwierdzanie, stabilność, rodzina
- Boundaries: nie będą mieć seksu dopóki nie zakończy związku

### Patterns (5):
1. **Fait accompli** (warning) — Sebastian podejmuje decyzje bez pytania
2. **Initiative check** (reminder) — monitoring kto inicjuje rozmowę
3. **Anxious attachment signal** (warning) — "gdzie jest haczyk?" etc.
4. **Non-verbal blindness** (reminder) — pytaj wprost o potrzeby
5. **Communication gap** (warning) — cisza godzinami → krótki ping

### Journal entries (3):
1. Dzień 1 (2026-03-24): Pierwsza rozmowa po latach. Natalka zainicjowała. Otwartość, vulnerabilność.
2. Dzień 3 (2026-03-26): Głęboka rozmowa o dzieciństwie, schematach. Identyczne potrzeby.
3. Dzień 6 (2026-03-29): Stabilna komunikacja. Natalka pytająca, Sebastian odpowiadający. Ryzyko: gdy ona przestanie pytać.

## E. Health Score — Gottman Framework

Score 1-10 bazowany na:
1. **Positivity ratio** — cel: 5:1 (pozytywne vs negatywne interakcje)
2. **Four Horsemen** check — criticism, contempt, defensiveness, stonewalling → -2 per horseman
3. **Initiative balance** — penalizacja gdy asymetria
4. **Communication quality** — regularność, głębokość
5. **Emotional safety** — czy obie strony czują się bezpiecznie
6. **Pattern alerts** — aktywne niebezpieczne wzorce obniżają score

## F. Bezpieczeństwo
- Router NIE montowany w main.py
- Brak structlog dla wrażliwych treści
- Tabele rel_* izolowane od reszty systemu
- Komentarz ostrzegawczy w pliku API
