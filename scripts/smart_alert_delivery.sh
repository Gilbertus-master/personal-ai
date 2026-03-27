#!/usr/bin/env bash
# smart_alert_delivery.sh — Proactive alert delivery via WhatsApp
# Delivers:
#   - Market alerts (relevance >= 80): immediate
#   - Competitor signals (severity = high): immediate
#   - Predictive alerts (probability >= 0.7): batched in morning
# Rules:
#   - Only 8:00-22:00 CET
#   - Max 5 alerts per day
#   - Dedup: don't send same alert twice
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.npm-global/bin:$PATH"

HOUR=$(date +%H)
if [ "$HOUR" -lt 8 ] || [ "$HOUR" -gt 22 ]; then
    echo "[$(date '+%F %T')] Outside hours (8-22). Skipping."
    exit 0
fi

.venv/bin/python - << 'PYEOF'
import subprocess, json, os, sys
from datetime import datetime, timezone
from app.db.postgres import get_pg_connection

os.environ['PATH'] = os.path.expanduser('~/.npm-global/bin') + ':' + os.environ['PATH']
TARGET = "+48505441635"
MAX_DAILY = 5

def send_wa(msg: str) -> bool:
    result = subprocess.run(
        ['openclaw', 'message', 'send', '--channel', 'whatsapp',
         '--target', TARGET, '--message', msg],
        capture_output=True, text=True, timeout=30)
    return result.returncode == 0

def _ensure_table():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alert_delivery_log (
                    id BIGSERIAL PRIMARY KEY,
                    alert_source TEXT NOT NULL,
                    alert_ref_id BIGINT,
                    message TEXT,
                    delivered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_alert_delivery_date
                    ON alert_delivery_log(delivered_at);
            """)
            conn.commit()

def was_delivered(source: str, ref_id: int) -> bool:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS(SELECT 1 FROM alert_delivery_log
                WHERE alert_source = %s AND alert_ref_id = %s
                AND delivered_at > NOW() - INTERVAL '7 days')
            """, (source, ref_id))
            return cur.fetchone()[0]

def log_delivery(source: str, ref_id: int, message: str):
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO alert_delivery_log (alert_source, alert_ref_id, message) VALUES (%s, %s, %s)",
                (source, ref_id, message[:500]))
            conn.commit()

def count_today() -> int:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM alert_delivery_log WHERE delivered_at >= CURRENT_DATE")
            return cur.fetchone()[0]

_ensure_table()
sent_today = count_today()
print(f"Alerts sent today: {sent_today}/{MAX_DAILY}")

if sent_today >= MAX_DAILY:
    print("Daily limit reached. Skipping.")
    sys.exit(0)

alerts_to_send = []

# 1. Market alerts (relevance >= 80, unacknowledged)
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT ma.id, ma.alert_level, ma.message, mi.relevance_score
            FROM market_alerts ma
            JOIN market_insights mi ON mi.id = ma.insight_id
            WHERE NOT ma.acknowledged
            AND mi.relevance_score >= 80
            ORDER BY mi.relevance_score DESC LIMIT 3
        """)
        for r in cur.fetchall():
            if not was_delivered("market_alert", r[0]):
                emoji = "🚨" if r[1] == "critical" else "⚡"
                alerts_to_send.append({
                    "source": "market_alert", "ref_id": r[0],
                    "msg": f"{emoji} *Rynek energii*\n\n{r[2]}\n\n_Relevance: {r[3]}/100_",
                    "ack_id": r[0]
                })

# 2. Competitor signals (severity = high, last 48h)
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT cs.id, c.name, cs.title, cs.description
            FROM competitor_signals cs
            JOIN competitors c ON c.id = cs.competitor_id
            WHERE cs.severity = 'high'
            AND cs.created_at > NOW() - INTERVAL '48 hours'
            ORDER BY cs.created_at DESC LIMIT 3
        """)
        for r in cur.fetchall():
            if not was_delivered("competitor_signal", r[0]):
                alerts_to_send.append({
                    "source": "competitor_signal", "ref_id": r[0],
                    "msg": f"🏢 *Konkurencja: {r[1]}*\n\n{r[2]}\n\n{r[3][:300]}",
                })

# 3. Predictive alerts (probability >= 0.7, active)
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, alert_type, prediction, probability, suggested_action
            FROM predictive_alerts
            WHERE status = 'active' AND probability >= 0.7
            ORDER BY probability DESC LIMIT 2
        """)
        for r in cur.fetchall():
            if not was_delivered("predictive_alert", r[0]):
                alerts_to_send.append({
                    "source": "predictive_alert", "ref_id": r[0],
                    "msg": f"🔮 *Predykcja: {r[1]}*\n\n{r[2]}\n\n_Prawdopodobieństwo: {float(r[3]):.0%}_\n\nZalecenie: {r[4]}",
                })

# Send (up to daily limit)
remaining = MAX_DAILY - sent_today
for alert in alerts_to_send[:remaining]:
    if send_wa(alert["msg"]):
        log_delivery(alert["source"], alert["ref_id"], alert["msg"])
        print(f"  Sent: [{alert['source']}] #{alert['ref_id']}")
        # Acknowledge market alerts
        if alert["source"] == "market_alert":
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE market_alerts SET acknowledged = TRUE WHERE id = %s", (alert["ref_id"],))
                    conn.commit()
    else:
        print(f"  Failed: [{alert['source']}] #{alert['ref_id']}")

print(f"\nDelivered: {min(len(alerts_to_send), remaining)}, Pending: {max(0, len(alerts_to_send) - remaining)}")
PYEOF
