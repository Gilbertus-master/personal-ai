# Part 5: Market, Finance & Process — Energy Intel, Budgets, Tech Radar

## Cel
Trzy connected moduły: Market Intelligence, Finance, Process Intelligence.

## Market
- Dashboard z energy market overview
- Insights feed (latest market intelligence)
- Competitor landscape: tabela, add, scan, analyze detail, signals timeline
- Market alerts: acknowledge/dismiss
- RSS sources management

## Finance
- Budget overview: daily/module spend vs limit, utilization bars
- API cost tracker: per model, per module, trend charts
- Goals: lista, create, update progress, AI risk analysis

## Process Intelligence
- Dashboard: business lines, process discovery
- App inventory: lista, deep analysis, cost analysis, ranking
- Tech radar: quadrant chart (adopt/trial/assess/hold)
- Data flows: visualization
- Automation roadmap: timeline
- Workforce analysis: per-employee automation potential (CEO only)

## API Endpoints
Market: `/market/*`, `/competitors/*`
Finance: `/finance/*`, `/costs/*`, `/goals/*`
Process: `/process-intel/*`

## RBAC
- Market: director+
- Competitors: board+
- Finance: board+
- Process intel: director+
- Workforce analysis: ceo only
- Tech radar: board+
