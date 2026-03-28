#!/usr/bin/env bash
# activate_dormant_modules.sh — Activate modules that were built but dormant
# Run after Omnius is connected and data is flowing from REH/REF
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true

echo "=== Activating dormant modules ==="

python - << 'PYEOF'
import json
from app.db.postgres import get_pg_connection

modules_status = {}

# 1. Financial metrics — seed from API costs + create structure
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM financial_metrics")
        count = cur.fetchone()[0]
        if count == 0:
            # Seed from api_costs
            cur.execute("""
                INSERT INTO financial_metrics (company, metric_type, value, period_start, period_end, source)
                SELECT 'Gilbertus', 'api_costs',
                       ROUND(SUM(cost_usd)::numeric, 2),
                       DATE_TRUNC('month', created_at)::date,
                       (DATE_TRUNC('month', created_at) + INTERVAL '1 month')::date,
                       'api_costs_auto'
                FROM api_costs
                WHERE cost_usd > 0
                GROUP BY DATE_TRUNC('month', created_at)
                HAVING SUM(cost_usd) > 0
                ON CONFLICT DO NOTHING
            """)
            conn.commit()
            cur.execute("SELECT COUNT(*) FROM financial_metrics")
            count = cur.fetchone()[0]
            modules_status["financial_metrics"] = f"Seeded {count} records from API costs"
        else:
            modules_status["financial_metrics"] = f"Already has {count} records"

# 2. Commitments — check extraction
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM commitments")
        count = cur.fetchone()[0]
        modules_status["commitments"] = f"{count} records" + (" (extraction cron active)" if count > 0 else " — check extract_commitments cron")

# 3. Sentiment scores
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='sentiment_scores')")
        exists = cur.fetchone()[0]
        if exists:
            cur.execute("SELECT COUNT(*) FROM sentiment_scores")
            count = cur.fetchone()[0]
            modules_status["sentiment_scores"] = f"{count} records"
        else:
            modules_status["sentiment_scores"] = "Table does not exist — run sentiment_tracker"

# 4. Delegation tasks
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='delegation_tasks')")
        exists = cur.fetchone()[0]
        if exists:
            cur.execute("SELECT COUNT(*) FROM delegation_tasks")
            count = cur.fetchone()[0]
            modules_status["delegation_tasks"] = f"{count} records"
        else:
            modules_status["delegation_tasks"] = "Table does not exist — run delegation_chain"

# 5. Meeting minutes
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='meeting_minutes')")
        exists = cur.fetchone()[0]
        if exists:
            cur.execute("SELECT COUNT(*) FROM meeting_minutes")
            count = cur.fetchone()[0]
            modules_status["meeting_minutes"] = f"{count} records"
        else:
            modules_status["meeting_minutes"] = "Table does not exist — run generate_minutes"

# 6. Action outcomes
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='action_outcomes')")
        exists = cur.fetchone()[0]
        if exists:
            cur.execute("SELECT COUNT(*) FROM action_outcomes")
            count = cur.fetchone()[0]
            modules_status["action_outcomes"] = f"{count} records"
        else:
            modules_status["action_outcomes"] = "Table does not exist — run action_outcome_tracker"

# 7. Decisions
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM decisions")
        count = cur.fetchone()[0]
        modules_status["decisions"] = f"{count} records"

print("\n=== Module Status ===")
for mod, status in sorted(modules_status.items()):
    icon = "✅" if "records" in status and not status.startswith("0 ") else "⚠️"
    print(f"  {icon} {mod}: {status}")

print(f"\nTotal modules checked: {len(modules_status)}")
PYEOF

echo ""
echo "=== Done ==="
