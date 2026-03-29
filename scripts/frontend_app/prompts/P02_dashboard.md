# Part 2: Dashboard & Alerts — Brief, KPIs, Timeline, Notifications

## Cel
Strona główna po zalogowaniu. Morning brief, alerty, KPI cards, timeline, status systemu.

## Funkcjonalności
1. **Morning Brief** — pełny brief z `/brief/today`, renderowany jako Markdown z sekcjami
2. **Alerts Feed** — aktywne alerty z `/alerts`, severity color-coded, dismiss/acknowledge
3. **KPI Grid** — karty z kluczowymi metrykami:
   - Chunks / Events / Entities count (z `/status`)
   - Open commitments (z `/commitments?status=open`)
   - API costs today (z `/costs/budget`)
   - Extraction coverage (z DB stats)
4. **Activity Timeline** — ostatnie zdarzenia z `/timeline` (scrollable, filtrable po typie)
5. **System Status** — health checks: Postgres, Qdrant, Whisper, API, Crons (z `/status`)
6. **Quick Actions** — buttons: "Nowy czat", "Meeting Prep", "Scan Market", "Compliance Check"
7. **Notifications Bell** — w topbar, real-time alerty (polling co 60s)

## RBAC
- CEO/gilbertus_admin: pełny dashboard
- Board: brief + KPIs + timeline (bez system status)
- Director/Manager: brief (ogólny) + calendar widget
- Specialist: uproszczony — own tasks + calendar
- Operator: TYLKO system status i cron health

## API Endpoints
- `GET /brief/today` — morning brief
- `GET /alerts` — active alerts
- `GET /status` — system dashboard
- `POST /timeline` — event timeline (event_type, date_from, limit)
- `GET /costs/budget` — budget status
- `GET /commitments?status=open` — open commitments count
- `GET /observability/dashboard` — latency, errors, cost metrics

## UX
- Grid layout: 2 kolumny na desktop (brief left, alerts+KPIs right), 1 na mobile
- KPI cards: number + trend arrow (↑↓) + sparkline chart
- Brief: collapsible sekcje (Events, Alerts, Commitments, Compliance)
- Auto-refresh: co 5 min
- Skeleton loaders na initial load
