# Part 3: People & Intelligence — Directory, Profiles, Sentiment, Opportunities, Scenarios

## Cel
Moduł zarządzania ludźmi + business intelligence. Dwa connected moduły w jednym Part.

## People
1. **Directory** — lista osób z search, filtry (rola, organizacja, status), sortowanie
2. **Profile** — per-person page: scorecard, timeline, open loops, sentiment chart, delegation
3. **Evaluation** — trigger AI evaluation, history of evaluations
4. **Network Graph** — wizualizacja sieci relacji (d3-force lub react-force-graph)
5. **Wellbeing** — trend charts (board+ only)

## Intelligence
1. **Opportunities** — tabela ranked by ROI, scan trigger, status tracking
2. **Inefficiencies** — raport z `/inefficiency`, Markdown render
3. **Correlations** — explorer: wybierz typ (temporal/person/anomaly/report), parametry, wynik
4. **Scenarios** — CRUD: lista, create, analyze impact, compare 2 scenarios
5. **Predictions** — predictive alerts z `/predictions`
6. **Org Health** — assessment score + trend

## API Endpoints (People)
- `GET /people` — list
- `GET /people/{slug}` — detail
- `POST /people` — create
- `GET /scorecard/{slug}` — employee scorecard
- `GET /sentiment/{slug}` — sentiment trend
- `GET /delegation/{slug}` — delegation effectiveness
- `GET /network` — communication network
- `POST /evaluate` — trigger evaluation
- `GET /wellbeing` — wellbeing score

## API Endpoints (Intelligence)
- `GET /opportunities` — list
- `POST /opportunities/scan` — scan
- `GET /inefficiency` — report
- `POST /correlate` — correlation analysis
- `GET /scenarios`, `POST /scenarios`, `POST /scenarios/{id}/analyze`
- `GET /predictions` — predictive alerts
- `GET /org-health`, `POST /org-health/assess`

## RBAC
- People directory: director+ (own department), ceo+ (all)
- Evaluations: ceo only
- Sentiment/wellbeing: board+
- Intelligence: board+
- Scenarios: ceo+
- Network graph: board+
