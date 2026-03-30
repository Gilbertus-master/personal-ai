# Universal Interaction Layer — Plan Architektoniczny

## Wizja
Każda informacja w Gilbertus App (insight, alert, decyzja, sprawa compliance, event kalendarzowy, okazja rynkowa) 
jest "actionable" — użytkownik może na niej wykonać ustandaryzowany zestaw akcji.
Wszystkie akcje są audytowane i widoczne dla przełożonego.

## Warstwa 1: Universal Action Menu (Frontend)

### Komponent <ActionableItem> — owija KAŻDY element w każdym module
```tsx
<ActionableItem
  itemId="opp_123"
  itemType="opportunity"
  itemTitle="Okazja: klient X - 50 GWh"
  itemContent={fullJSON}
  context="market"
>
  {/* dowolny istniejący komponent */}
  <OpportunityCard ... />
</ActionableItem>
```

### Menu akcji (bottom sheet / right-click / "..." button):
1. 🔍 **Zbadaj głębiej** — otwiera research panel, Gilbertus robi pogłębioną analizę
2. 💬 **Komentarz** — dodaj notatkę/komentarz do tego elementu
3. ⭐ **Oceń** — pomocne/niepomocne/błędne wskazanie (z opcjonalnym powodem)
4. 📋 **Zlec zadanie** — stwórz task dla Gilbertusa powiązany z tym elementem
5. 🚫 **Błędne wskazanie** — oznacz jako false positive + powód (trafia do przełożonego)
6. ➡️ **Przekaż dalej** — wybierz osobę z hierarchii, dodaj notatkę

### Zachowanie akcji:
- Każda akcja → zapis w `user_activity_log`
- Akcja "Błędne wskazanie" → notyfikacja do przełożonego
- Akcja "Przekaż dalej" → task w systemie dla wybranej osoby
- Akcja "Zbadaj głębiej" → POST /ask z enhanced prompt, wynik zapisany w `item_annotations`

## Warstwa 2: Backend — Audit & Annotation System

### Tabele:
```sql
-- Log wszystkich akcji użytkowników
CREATE TABLE user_activity_log (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL DEFAULT 'sebastian',
  session_id TEXT,
  action_type TEXT NOT NULL,  -- 'research', 'comment', 'rate', 'task', 'flag', 'forward', 'view'
  item_id TEXT NOT NULL,
  item_type TEXT NOT NULL,    -- 'opportunity', 'alert', 'decision', 'compliance_matter', etc.
  item_title TEXT,
  item_context TEXT,          -- moduł: 'market', 'compliance', 'intelligence', etc.
  payload JSONB,              -- {comment, rating, task_instruction, forward_to, reason}
  ip_address TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Adnotacje do elementów (komentarze, oceny, badania)
CREATE TABLE item_annotations (
  id BIGSERIAL PRIMARY KEY,
  item_id TEXT NOT NULL,
  item_type TEXT NOT NULL,
  user_id TEXT DEFAULT 'sebastian',
  annotation_type TEXT NOT NULL,  -- 'comment', 'rating', 'research_result', 'flag', 'task'
  content TEXT,
  rating INTEGER CHECK (rating BETWEEN 1 AND 5),
  is_false_positive BOOLEAN DEFAULT FALSE,
  research_result TEXT,
  task_id INTEGER REFERENCES alert_fix_tasks(id),
  forward_to TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Hierarchia użytkowników
CREATE TABLE user_hierarchy (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  manager_id TEXT NOT NULL,
  organization TEXT DEFAULT 'REH',
  role TEXT DEFAULT 'specialist',
  active BOOLEAN DEFAULT TRUE,
  UNIQUE(user_id, organization)
);

-- Raporty aktywności (generowane przez Gilbertusa)
CREATE TABLE activity_reports (
  id SERIAL PRIMARY KEY,
  report_type TEXT NOT NULL,      -- 'daily', 'weekly', 'manager_summary'
  target_user TEXT,               -- null = wszystkie
  manager_id TEXT,
  period_start TIMESTAMPTZ,
  period_end TIMESTAMPTZ,
  summary TEXT,
  data JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Endpointy:
- POST /activity/log          — log akcji użytkownika
- GET  /activity/log          — historia akcji (filtrowanie po user, type, period)
- POST /items/{id}/annotate   — dodaj adnotację do elementu
- GET  /items/{id}/annotations — pobierz adnotacje dla elementu
- GET  /activity/report/daily — dzienny raport aktywności
- GET  /activity/report/manager/{user_id} — raport dla przełożonego
- POST /activity/research/{item_id} — zlec pogłębiony research
- GET  /hierarchy/team        — pobierz członków zespołu
- POST /hierarchy/forward     — przekaż element do innej osoby

## Warstwa 3: Manager Dashboard

### Strona /admin/activity
- Dzienny/tygodniowy timeline akcji Sebastiana
- Heatmapa: które moduły używane najczęściej
- Lista flagowanych elementów ("błędne wskazanie") — do review
- Lista oddelegowanych zadań i ich status
- Trendy: ile insightów odrzuconych vs zaakceptowanych
- Alert: jeśli wzorzec odrzuceń wskazuje na systemowy problem

### Strona /admin/team (dla przełożonego)
- Raport per pracownik: co robił, co odrzucał, co flagował
- Klikalne: przełożony może zatwierdzić/odrzucić flagę "błędne wskazanie"
- Feed aktywności całego zespołu (chronologiczny)

## Warstwa 4: Audyt Ciągły (Gilbertus + Omnius)

### Gilbertus Audit Cron (codziennie 7:00):
1. Pobierz aktywności z ostatnich 24h
2. Wykryj anomalie (nagłe wzrosty flagowania, brak aktywności >48h)
3. Generuj raport dla przełożonego
4. Wyślij alert jeśli wzorzec wymaga uwagi

### Omnius Integration (przyszłość):
- Ten sam `user_activity_log` używany przez Omnius
- Cross-system analytics: Gilbertus insights → akcje w Omnius → wyniki biznesowe
- Feedback loop: jeśli insight był "błędny" → model się uczy

## Priorytety Implementacji

### P0 (teraz — sprint 1):
- [ ] ActionableItem komponent (universal wrapper)
- [ ] 6 akcji w menu (research, comment, rate, task, flag, forward)
- [ ] Backend: user_activity_log + item_annotations tables + API
- [ ] Integration w 3 kluczowych modułach: Market, Intelligence, Compliance

### P1 (sprint 2):
- [ ] Integration we wszystkich modułach
- [ ] /admin/activity — raport aktywności
- [ ] Audit cron (7:00 daily)
- [ ] Przełożony może reviewować flagi

### P2 (sprint 3):
- [ ] user_hierarchy table + UI
- [ ] Manager dashboard z teamem
- [ ] Omnius integration
- [ ] Activity-based feedback do modeli
