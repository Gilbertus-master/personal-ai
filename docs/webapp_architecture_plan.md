# Gilbertus WebApp — Architecture Plan

**Data:** 2026-03-30
**Status:** Active

## 1. Obecny Stan

Frontend jest **~95% zbudowany** jako monorepo pnpm:
- **Next.js 16** + React 19 + TypeScript 5.7
- **Tailwind CSS 4** z ciemnym motywem (CSS vars)
- **React Query v5** (server state) + **Zustand** (client state)
- **@gilbertus/api-client** — 37 plików z pełnym klientem API
- **@gilbertus/ui** — 100+ komponentów w bibliotece
- **@gilbertus/rbac** — 7 ról, dynamiczna nawigacja
- **23 hooki** do pobierania danych
- **15+ stron** z żywymi danymi z API (190+ endpointów)

### Moduły w pełni działające:
- Dashboard (KPI, brief, alerts, timeline, status)
- Chat (sidebar, wiadomości, quick actions, historia konwersacji)
- Compliance (dashboard, matters, obligations, deadlines, risks, RACI, documents, trainings)
- Market (dashboard, insights, competitors, signals, sources)
- Finance (dashboard, metrics, budgets, costs, goals)
- People (table, profiles, network, delegation)
- Process (business lines, processes, apps, flows, tech radar, workforce)
- Decisions (journal, patterns, intelligence, outcomes)
- Calendar (week view, meeting prep, minutes, analytics, deep work)
- Voice (WebSocket, sessions, recording, TTS)
- Admin (status, crons, code review, audit, terminal, costs, users)
- Documents (search, upload, ingestion)
- Settings

### Kluczowe luki:
1. **Morning Brief** — brak dedykowanej strony z historią dzień po dniu + wykonywalnymi zadaniami
2. **Context Chat Widget** — brak mini-chatu w kontekście każdego modułu
3. **Intelligence** — 3 placeholderowe taby (correlations, scenarios, predictions)

## 2. Struktura Nawigacji (sidebar)

Już zaimplementowana w `packages/rbac/src/navigation.ts`:

```
🧠 Gilbertus
├── 📋 Dashboard (overview)
├── 🌅 Morning Brief ← NOWE (dedykowana strona)
├── 💬 Chat (konwersacja z Gilbertusem)
├── 📊 Intelligence (insights, scenarios, blind spots, predictions)
├── ⚖️ Compliance (dashboard, matters, obligations, deadlines, risks, RACI, documents, trainings)
├── 💰 Finance (dashboard, costs, goals)
├── 📈 Market (dashboard, competitors, alerts, signals, sources)
├── 👥 People (table, profiles, network)
├── ⚙️ Process (dashboard, apps, flows, tech radar, workforce)
├── 📋 Decisions (journal, patterns, intelligence)
├── 📅 Calendar (events, meeting prep, minutes, analytics)
├── 📄 Documents (search, browse, ingestion)
├── 🎙️ Voice (sessions, recording)
├── 🤖 Admin (status, crons, code review, audit, terminal, costs, users)
└── ⚙️ Settings
```

## 3. Nowe Komponenty do Zbudowania

### 3.1 Morning Brief Page (`/brief`)

**Cel:** Dedykowana strona z historią briefów dzień po dniu, nawigacją kalendarzową, i wykonywalnymi zadaniami.

**Architektura:**
```
BriefPage
├── BriefDateNavigator — nawigacja dzień po dniu (← wczoraj | dziś | jutro →)
├── BriefContent — treść briefu (MarkdownRenderer)
├── BriefTaskList — lista zadań z API z przyciskami "Wykonaj"
│   └── BriefTaskItem — pojedyncze zadanie z akcją
├── BriefMeta — statystyki (events, entities, open loops)
└── ContextChatWidget — mini-chat w kontekście briefu
```

**API:**
- `GET /brief/today` — dzisiejszy brief
- `GET /brief/today?date=YYYY-MM-DD` — brief na wybraną datę (do sprawdzenia)
- `POST /summary/query` — historia briefów

**Hook:** `useBriefHistory(date: string)`

### 3.2 Context Chat Widget

**Cel:** Floating mini-chat dostępny z każdego modułu, wysyłający pytania z kontekstem aktualnego modułu.

**Architektura:**
```
ContextChatWidget (fixed bottom-right)
├── ChatToggleButton — przycisk z ikoną (collapsed)
├── ChatPanel (expanded)
│   ├── ChatHeader — tytuł + context badge + close
│   ├── MessageList — historia wiadomości (max 50)
│   ├── ChatInput — pole tekstowe + send
│   └── SuggestedQuestions — 3 sugerowane pytania dla kontekstu
```

**Konteksty:**
- `brief` → "Pytasz o dzisiejszy brief..."
- `compliance` → "Pytasz w kontekście compliance..."
- `market` → "Pytasz o market intelligence..."
- itd.

**API:** `POST /ask` z dodanym prefixem kontekstu w query

### 3.3 Intelligence Tabs

**Cel:** Wypełnienie 3 placeholderowych tabów na stronie Intelligence.

**Tabs:**
1. **Scenarios** — `GET /scenarios`, `POST /scenarios`, `POST /scenarios/{id}/analyze`
2. **Correlations** — `POST /correlate` z typami: temporal, person, anomaly, report
3. **Predictions** — `GET /predictions`

## 4. Wzorzec Komponentu

Każdy nowy komponent:
1. **TypeScript strict** — zero `any`
2. **React Query** — `useQuery`/`useMutation` z auto-refresh
3. **Loading skeleton** — animacja podczas ładowania
4. **Error boundary** — graceful error z retry
5. **Responsywny** — mobile-first z Tailwind
6. **Ciemny motyw** — CSS vars (`var(--surface)`, `var(--text)`, etc.)
7. **Role-based** — RBAC gate gdzie potrzebne

## 5. Plan Implementacji

### Krok 1: Foundation
- Dodaj `/brief` route do nawigacji
- Stwórz `useBriefHistory` hook
- Dodaj `fetchBriefByDate` do API client

### Krok 2: Morning Brief Page
- `BriefDateNavigator` — nawigacja datą
- `BriefContent` — renderowanie markdown
- `BriefTaskList` — lista zadań z akcjami
- `BriefMeta` — statystyki

### Krok 3: Context Chat Widget
- `ContextChatWidget` — floating panel
- Integracja z `POST /ask`
- Dodanie do app layout
- Kontekst-aware suggested questions

### Krok 4: Intelligence Tabs
- `ScenariosTab` — lista scenariuszy + tworzenie
- `CorrelationsTab` — analiza korelacji
- `PredictionsTab` — predykcje alertów

## 6. File Structure

```
frontend/
├── apps/web/app/(app)/
│   ├── brief/
│   │   └── page.tsx              ← NOWE
│   └── intelligence/
│       └── page.tsx              ← ROZSZERZONE
├── packages/ui/src/components/
│   ├── brief/
│   │   ├── brief-date-navigator.tsx   ← NOWE
│   │   ├── brief-task-list.tsx        ← NOWE
│   │   └── index.ts                   ← NOWE
│   ├── context-chat/
│   │   ├── context-chat-widget.tsx    ← NOWE
│   │   └── index.ts                   ← NOWE
│   └── intelligence/
│       ├── scenarios-tab.tsx          ← NOWE
│       ├── correlations-tab.tsx       ← NOWE
│       └── predictions-tab.tsx        ← NOWE
├── packages/api-client/src/
│   └── dashboard.ts                   ← ROZSZERZONE (briefByDate)
└── apps/web/lib/hooks/
    └── use-dashboard.ts               ← ROZSZERZONE (useBriefHistory)
```
