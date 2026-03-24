#!/usr/bin/env bash
# send_insights_to_whatsapp.sh — Sends new unsent insights to Sebastian via WhatsApp.
# Runs every 30 min via cron.
set -euo pipefail
cd "$(dirname "$0")/.."

.venv/bin/python -c "
import subprocess, json
from app.db.postgres import get_pg_connection

# 1. Find insights not yet sent (reviewed=false, type=recommendation)
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT id, insight_type, area, title, description, confidence
            FROM insights
            WHERE reviewed = false
            ORDER BY confidence DESC, created_at DESC
            LIMIT 3
        ''')
        unsent = cur.fetchall()

if not unsent:
    print('No new insights to send')
    exit(0)

for row in unsent:
    iid, itype, area, title, desc, conf = row

    # Format message
    emoji = {'trading':'📈','business':'🏢','relationships':'👥','wellbeing':'💚','general':'🧠'}.get(area,'💡')
    msg = f'{emoji} *{title}*\n\n{desc[:800]}\n\n_Confidence: {conf:.0%} | Area: {area}_\n\nOceń: 👍/👎 lub zadaj pytanie'

    # Send via OpenClaw
    result = subprocess.run(
        ['openclaw', 'message', 'send', '--channel', 'whatsapp',
         '--target', '+48505441635', '--message', msg],
        capture_output=True, text=True, timeout=30,
    )

    if result.returncode == 0:
        print(f'Sent: {title[:50]}')
        # Mark as sent
        with get_pg_connection() as conn2:
            with conn2.cursor() as cur2:
                cur2.execute('UPDATE insights SET reviewed = true WHERE id = %s', (iid,))
            conn2.commit()
    else:
        print(f'Failed to send: {result.stderr[:100]}')
"
