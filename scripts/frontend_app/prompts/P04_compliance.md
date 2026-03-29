# Part 4: Compliance & Legal — Matters, Documents, Trainings, Risks, RACI

## Cel
Pełny moduł compliance z 40+ endpointami. Dashboard, sprawy, dokumenty, szkolenia, ryzyka, RACI.

## Funkcjonalności
1. **Dashboard** — 9 obszarów compliance, overdue counts, risk levels, fazy spraw
2. **Matters** — lista z filtrami (status, priority, area), detail z akcjami (research, advance, report)
3. **Obligations** — tracker z deadlinami, fulfillment status, overdue alerts
4. **Deadlines** — kalendarzowy widok z color-coded urgency
5. **Documents** — lista, generowanie via AI, approve/sign workflow, stale doc alert
6. **Trainings** — lista, status per osoba, create training, complete
7. **Risks** — rejestr ryzyk, heatmap (probability × impact matrix), mitigation plans
8. **RACI** — matryca Responsible/Accountable/Consulted/Informed per area/obligation
9. **Reports** — daily, weekly, area-specific, generowane on-demand

## API Endpoints (40+)
All under `/compliance/`:
- `GET /dashboard`, `GET /areas`, `GET /areas/{code}`
- `GET /matters`, `POST /matters`, `GET /matters/{id}`, `POST /matters/{id}/research`, `POST /matters/{id}/advance`, `POST /matters/{id}/report`
- `GET /obligations`, `GET /obligations/overdue`, `POST /obligations`, `POST /obligations/{id}/fulfill`
- `GET /deadlines`, `GET /deadlines/overdue`
- `GET /documents`, `GET /documents/stale`, `POST /documents/generate`, `POST /documents/{id}/approve`, `POST /documents/{id}/sign`
- `GET /trainings`, `POST /trainings`, `POST /trainings/{id}/complete`
- `GET /risks`, `GET /risks/heatmap`
- `GET /raci`, `POST /raci`
- `GET /report/daily`, `GET /report/weekly`, `GET /report/area/{code}`

## RBAC
- Dashboard: director+
- Matters CRUD: board+
- Documents generate/approve: ceo+
- Trainings: director+ (view), board+ (create)
- Risks: board+
- RACI: board+
