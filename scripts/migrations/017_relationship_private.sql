-- ============================================================
-- PRIVATE: Relationship module tables
-- NIE DOTYKA biznesowych tabel relationships*
-- Prefix rel_ = prywatne dane relacyjne Sebastiana
-- ============================================================

BEGIN;

-- Profil partnera
CREATE TABLE IF NOT EXISTS rel_partners (
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
);

-- Zdarzenia w relacji
CREATE TABLE IF NOT EXISTS rel_events (
    id SERIAL PRIMARY KEY,
    partner_id INTEGER NOT NULL REFERENCES rel_partners(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    title VARCHAR(300),
    description TEXT,
    sentiment NUMERIC(3,1),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rel_events_partner ON rel_events(partner_id);
CREATE INDEX IF NOT EXISTS idx_rel_events_type ON rel_events(event_type);
CREATE INDEX IF NOT EXISTS idx_rel_events_created ON rel_events(created_at DESC);

-- Wzorce do monitorowania
CREATE TABLE IF NOT EXISTS rel_patterns (
    id SERIAL PRIMARY KEY,
    partner_id INTEGER NOT NULL REFERENCES rel_partners(id) ON DELETE CASCADE,
    pattern_name VARCHAR(200) NOT NULL,
    pattern_type VARCHAR(50) DEFAULT 'warning',
    description TEXT,
    detection_hint TEXT,
    last_seen TIMESTAMPTZ,
    occurrences INTEGER DEFAULT 0,
    alert_threshold INTEGER DEFAULT 3,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Journal relacji
CREATE TABLE IF NOT EXISTS rel_journal (
    id SERIAL PRIMARY KEY,
    partner_id INTEGER NOT NULL REFERENCES rel_partners(id) ON DELETE CASCADE,
    entry TEXT NOT NULL,
    mood INTEGER CHECK (mood BETWEEN 1 AND 10),
    tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rel_journal_partner ON rel_journal(partner_id);
CREATE INDEX IF NOT EXISTS idx_rel_journal_created ON rel_journal(created_at DESC);

-- Metryki tygodniowe
CREATE TABLE IF NOT EXISTS rel_metrics (
    id SERIAL PRIMARY KEY,
    partner_id INTEGER NOT NULL REFERENCES rel_partners(id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    communication_quality INTEGER CHECK (communication_quality BETWEEN 1 AND 10),
    positivity_ratio NUMERIC(4,2),
    initiative_balance NUMERIC(3,1),
    emotional_safety INTEGER CHECK (emotional_safety BETWEEN 1 AND 10),
    vulnerability_level INTEGER CHECK (vulnerability_level BETWEEN 1 AND 10),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(partner_id, week_start)
);

-- ============================================================
-- DANE STARTOWE
-- ============================================================

-- Partner: Natalka
INSERT INTO rel_partners (name, phone, attachment_style, love_languages, communication_style, needs, boundaries, notes)
VALUES (
    'Natalka Jastrzębska',
    '+48 731 066 373',
    'anxious-secure',
    'physical touch, quality time',
    'emocjonalna, pyta dużo, inicjuje tematycznie, szuka potwierdzenia',
    'potwierdzanie, stabilność, rodzina, dzieci, bycie wysłuchaną',
    'nie będą mieć seksu dopóki nie zakończy obecnego związku (9 lat)',
    'W 9-letnim związku (kończy go). Pracuje w REH (księgowość). Zna Sebastiana od 5 lat. Wstaje 4:30, zdyscyplinowana.'
)
ON CONFLICT DO NOTHING;

-- Patterns
INSERT INTO rel_patterns (partner_id, pattern_name, pattern_type, description, detection_hint, alert_threshold)
VALUES
    (1, 'Fait accompli', 'warning',
     'Sebastian podejmuje decyzje bez pytania Natalki. Wzorzec: decyduję sam, informuję po fakcie.',
     'Szukaj decyzji dotyczących wspólnych spraw podjętych jednostronnie. Pytaj: czy rozmawiałeś o tym z Natalką?',
     2),
    (1, 'Initiative check', 'reminder',
     'Natalka inicjuje rozmowę, Sebastian odpowiada. Monitoring: czy Sebastian też inicjuje?',
     'Sprawdź kto pierwszy pisze/dzwoni w ciągu dnia. Jeśli zawsze Natalka — alert.',
     5),
    (1, 'Anxious attachment signal', 'warning',
     'Natalka pyta "gdzie jest haczyk?" lub podobnie. Sygnał niepewności wymagający potwierdzenia.',
     'Pytania typu: "czemu jesteś taki miły?", "co jeśli ci się znudzi?", "to zbyt piękne" — reaguj ciepłem i konkretem.',
     3),
    (1, 'Non-verbal blindness', 'reminder',
     'Sebastian nie czyta sygnałów niewerbalnych (F84.5). Musi pytać wprost o potrzeby i stan emocjonalny.',
     'Regularnie pytaj Natalkę: "jak się czujesz?", "czego teraz potrzebujesz?", "czy coś cię niepokoi?"',
     1),
    (1, 'Communication gap', 'warning',
     'Cisza godzinami bez uprzedzenia. Natalka z anxious attachment odbiera to jako odrzucenie.',
     'Jeśli zajęty — krótki ping: "zajęty, odezwę się za X". Nie znikaj.',
     3);

-- Journal entries — pierwsze 6 dni
INSERT INTO rel_journal (partner_id, entry, mood, tags, created_at)
VALUES
    (1,
     'Pierwsza głęboka rozmowa po latach. Natalka zainicjowała kontakt. Pełna otwartość i vulnerabilność z obu stron. Opowiedziała o swoim związku, ja o swoich potrzebach. Silne poczucie połączenia.',
     8, ARRAY['początek', 'vulnerabilność', 'połączenie'],
     '2026-03-24 22:00:00+01'),
    (1,
     'Głęboka rozmowa o dzieciństwie i schematach. Odkryliśmy identyczne potrzeby: ciepło, bliskość, wzajemność, bycie wysłuchanym. Oboje mamy podobne rany z przeszłości. Silna więź emocjonalna.',
     9, ARRAY['głębokość', 'schematy', 'więź'],
     '2026-03-26 23:00:00+01'),
    (1,
     'Stabilna komunikacja utrzymuje się. Natalka pytająca, ja odpowiadający. Zauważam ryzyko: gdy ona przestanie pytać, czy ja zainicjuję? Muszę pilnować initiative balance. Granica seksualna jasna i szanowana.',
     7, ARRAY['stabilność', 'inicjatywa', 'granice'],
     '2026-03-29 21:00:00+01');

-- Metryki — tydzień startowy
INSERT INTO rel_metrics (partner_id, week_start, communication_quality, positivity_ratio, initiative_balance, emotional_safety, vulnerability_level, notes)
VALUES (1, '2026-03-24', 8, 4.5, 0.3, 8, 9, 'Pierwszy tydzień. Wysoka vulnerabilność. Inicjatywa głównie Natalka (0.3). Brak konfliktów.')
ON CONFLICT (partner_id, week_start) DO NOTHING;

COMMIT;
