#!/usr/bin/env bash
# weekly_report.sh — Generate automated weekly report.
# 3 sections: per-company (via Omnius), cross-company comparison, personal summary.
# Cron: 0 20 * * 0 (Sunday 20:00 CET, before architecture review at 22:00)
set -uo pipefail
cd "$(dirname "$0")/.."

.venv/bin/python << 'PYTHON'
import json
import os
from datetime import datetime, timedelta

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

now = datetime.now()
week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
week_end = now.strftime("%Y-%m-%d")

print(f"=== Weekly Report: {week_start} to {week_end} ===")

# Collect data
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        # Events this week
        cur.execute("""
            SELECT event_type, COUNT(*) FROM events
            WHERE event_time >= %s AND event_time < %s
            GROUP BY event_type ORDER BY count DESC
        """, (week_start, week_end))
        events = {r[0]: r[1] for r in cur.fetchall()}

        # Active people
        cur.execute("""
            SELECT en.canonical_name, COUNT(DISTINCT ee.event_id) as events
            FROM entities en
            JOIN event_entities ee ON ee.entity_id = en.id
            JOIN events e ON e.id = ee.event_id
            WHERE en.entity_type = 'person' AND e.event_time >= %s AND e.event_time < %s
            GROUP BY en.canonical_name ORDER BY events DESC LIMIT 15
        """, (week_start, week_end))
        people = [(r[0], r[1]) for r in cur.fetchall()]

        # Decisions this week
        cur.execute("SELECT decision_text, area FROM decisions WHERE decided_at >= %s AND decided_at < %s", (week_start, week_end))
        decisions = [(r[0], r[1]) for r in cur.fetchall()]

        # Alerts
        cur.execute("SELECT alert_type, title FROM alerts WHERE created_at >= %s ORDER BY created_at DESC LIMIT 10", (week_start,))
        alerts = [(r[0], r[1]) for r in cur.fetchall()]

        # API costs
        cur.execute("SELECT ROUND(SUM(cost_usd)::numeric, 2) FROM api_costs WHERE created_at >= %s AND created_at < %s", (week_start, week_end))
        rows = cur.fetchall()
        api_cost = rows[0][0] if rows and rows[0][0] else 0

        # Insights this week
        cur.execute("SELECT title FROM insights WHERE created_at >= %s ORDER BY created_at DESC LIMIT 10", (week_start,))
        insights = [r[0] for r in cur.fetchall()]

# Try Omnius data
omnius_reports = {}
try:
    from app.omnius.client import list_tenants, get_omnius
    for tenant in list_tenants():
        try:
            omnius_reports[tenant] = get_omnius(tenant).get_nightly_report()
        except Exception:
            pass
except Exception:
    pass

# Build context
ctx = [
    f"Okres: {week_start} — {week_end}",
    f"\n=== WYDARZENIA ({sum(events.values())}) ===",
    json.dumps(events, ensure_ascii=False),
    f"\n=== AKTYWNE OSOBY ===",
]
for name, cnt in people[:10]:
    ctx.append(f"  {name}: {cnt} wydarzeń")

ctx.append(f"\n=== DECYZJE ({len(decisions)}) ===")
for text, area in decisions:
    ctx.append(f"  [{area}] {text[:100]}")

ctx.append(f"\n=== ALERTY ({len(alerts)}) ===")
for atype, title in alerts:
    ctx.append(f"  [{atype}] {title}")

ctx.append(f"\n=== INSIGHTY ({len(insights)}) ===")
for title in insights:
    ctx.append(f"  {title}")

ctx.append(f"\nKoszt API: ${api_cost}")

for tenant, report in omnius_reports.items():
    ctx.append(f"\n=== OMNIUS {tenant.upper()} ===")
    ctx.append(json.dumps(report, ensure_ascii=False, indent=2, default=str)[:1000])

context = "\n".join(ctx)

# Generate report
response = client.messages.create(
    model=MODEL,
    max_tokens=3000,
    temperature=0.2,
    system="""Jesteś Gilbertus Albans. Wygeneruj tygodniowy raport dla Sebastiana.

Sekcje:
## Podsumowanie tygodnia
3-5 najważniejszych rzeczy z tego tygodnia.

## Ludzie
Kto był najbardziej aktywny i w jakim kontekście.

## Decyzje i otwarte sprawy
Decyzje podjęte, sprawy nierozwiązane.

## Metryki
Liczby: wydarzenia, alerty, koszty API, postęp ekstrakcji.

## Rekomendacje na następny tydzień
Co Sebastian powinien zrobić w przyszłym tygodniu.

Pisz po polsku, konkretnie, z liczbami i nazwiskami.""",
    messages=[{"role": "user", "content": context}],
)

if hasattr(response, "usage"):
    log_anthropic_cost(MODEL, "weekly_report", response.usage)

report_text = "\n".join(b.text for b in response.content if hasattr(b, "text"))

# Save to summaries
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO summaries (summary_type, period_start, period_end, text)
            VALUES ('weekly_report', %s, %s, %s)
        """, (week_start, week_end, report_text))
    conn.commit()

print(report_text)
print(f"\n=== Report saved to summaries table ===")
PYTHON
