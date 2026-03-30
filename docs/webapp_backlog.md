# Gilbertus WebApp — Backlog

**Data:** 2026-03-30
**Status:** Active

## P0 — Critical (natychmiast)

- [x] Sidebar z pełną nawigacją wszystkich modułów (DONE — packages/rbac/navigation.ts)
- [x] API client z auto-refresh i loading states (DONE — 37 plików, React Query v5)
- [x] Dashboard z KPI, alerts, timeline, status (DONE)
- [x] Chat z historią konwersacji (DONE — layout.tsx)
- [ ] **Morning Brief page z historią dzień po dniu** — `/brief` route, date navigator, executable tasks
- [ ] **Context chat widget** — floating mini-chat z kontekstem modułu, dostępny wszędzie

## P1 — Tydzień 1

- [x] Legal/Compliance module — pełny CRUD + workflows (DONE — 13 sub-pages)
- [x] Decisions module — dziennik z outcomes (DONE — journal, patterns, intelligence)
- [x] Intelligence — insights + blind spots (DONE — org health, opportunities, inefficiency)
- [ ] **Intelligence — scenarios tab** — lista scenariuszy, tworzenie, analiza
- [ ] **Intelligence — correlations tab** — temporal, person, anomaly korelacje
- [ ] **Intelligence — predictions tab** — predykcje alertów

## P2 — Tydzień 2

- [x] Finance module — goals + costs z wykresami (DONE — metrics, budget, API costs)
- [x] Market module — competitors + signals (DONE — insights, alerts, sources)
- [x] People module — network + delegation (DONE — table, profiles, network page)
- [x] Calendar — events z meeting prep (DONE — week view, prep, minutes, analytics)

## P3 — Tydzień 3

- [x] Process module — apps + flows + tech radar (DONE — business lines, processes, optimizations)
- [x] Voice module — transkrypcje (DONE — WebSocket, sessions, recording)
- [x] Admin — status + crons + terminal (DONE — system status, cron manager, code review)
- [ ] Mobile-responsive fine-tuning

## Podsumowanie

| Kategoria | Gotowe | Do zrobienia |
|-----------|--------|--------------|
| Strony/Moduły | 15/15 | 0 |
| API Integration | 37 plików | +1 (briefByDate) |
| Hooki | 23 | +1 (useBriefHistory) |
| Nowe komponenty | — | 6 (brief page, context chat, 3 intelligence tabs) |
| Nowe routes | — | 1 (/brief) |

**90% frontendu jest gotowe. Brakuje 3 kluczowe rzeczy: Brief History, Context Chat, Intelligence Tabs.**
