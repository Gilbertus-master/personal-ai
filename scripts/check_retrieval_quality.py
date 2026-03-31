#!/usr/bin/env python3
"""Monitor retrieval quality and send alerts on degradation."""
import os, sys, subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

ALERT_FLAG = Path("/tmp/gilbertus_retrieval_alert")

def send_alert(msg):
    if ALERT_FLAG.exists():
        if datetime.now().timestamp() - ALERT_FLAG.stat().st_mtime < 3600:
            return
    subprocess.run(["openclaw", "message", "--to", "+48505441635", msg], timeout=10)
    ALERT_FLAG.touch()

import psycopg
conn_str = psycopg.conninfo.make_conninfo(
    host=os.getenv('POSTGRES_HOST','127.0.0.1'),
    port=int(os.getenv('POSTGRES_PORT','5432')),
    dbname=os.getenv('POSTGRES_DB','gilbertus'),
    user=os.getenv('POSTGRES_USER','gilbertus'),
    password=os.getenv('POSTGRES_PASSWORD','gilbertus')
)

try:
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN used_fallback THEN 1 ELSE 0 END) as fallbacks,
                    ROUND(AVG(retrieved_count)::numeric, 1) as avg_chunks,
                    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_ms)::numeric) as p95_ms
                FROM query_stage_times
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)
            row = cur.fetchone()
            if not row or row[0] == 0:
                print("No queries in last hour, skipping")
                sys.exit(0)

            total, fallbacks, avg_chunks, p95_ms = row
            fallback_pct = (fallbacks or 0) / total * 100

            alerts = []
            if fallback_pct > 20:
                alerts.append(f"⚠️ Query interpreter w trybie fallback: {fallback_pct:.0f}% zapytań ({fallbacks}/{total})")
            if avg_chunks and avg_chunks < 3:
                alerts.append(f"⚠️ Mało chunków w odpowiedziach: avg {avg_chunks} (oczekiwane >5)")
            if p95_ms and p95_ms > 30000:
                alerts.append(f"⚠️ System wolny: p95 latency = {p95_ms/1000:.0f}s (próg 30s)")

            if alerts:
                msg = "🔍 Gilbertus retrieval alert:\n" + "\n".join(alerts)
                send_alert(msg)
                print("Alert sent:", msg)
            else:
                ALERT_FLAG.unlink(missing_ok=True)
                print(f"OK: fallback={fallback_pct:.0f}%, avg_chunks={avg_chunks}, p95={p95_ms}ms")
except Exception as e:
    print(f"Check failed: {e}")
