#!/usr/bin/env bash
# send_insights_to_whatsapp.sh — Smart insight delivery
# Rules:
#   - Only sends between 8:00 and 22:00
#   - Only sends if Sebastian commented on previous insights (or first batch of the day)
#   - Max 3 insights per delivery
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.npm-global/bin:$PATH"

HOUR=$(date +%H)
if [ "$HOUR" -lt 8 ] || [ "$HOUR" -gt 22 ]; then
    echo "[$(date '+%F %T')] Outside hours (8-22). Skipping."
    exit 0
fi

.venv/bin/python -c "
import subprocess, json, os, sys
from datetime import datetime, timedelta
from app.db.postgres import get_pg_connection

os.environ['PATH'] = os.path.expanduser('~/.npm-global/bin') + ':' + os.environ.get('PATH','')

with get_pg_connection() as conn:
    with conn.cursor() as cur:
        # Check: how many insights were sent (reviewed=true) today?
        cur.execute('''
            SELECT count(*) FROM insights
            WHERE reviewed = true
            AND created_at >= CURRENT_DATE
        ''')
        sent_today = cur.fetchall()[0][0]

        # Check: were there any WhatsApp responses from Sebastian today?
        # (presence of whatsapp_live documents from today = Sebastian is active)
        cur.execute('''
            SELECT count(*) FROM documents d
            JOIN sources s ON d.source_id = s.id
            WHERE s.source_type IN ('whatsapp_live')
            AND d.created_at >= CURRENT_DATE
        ''')
        wa_activity = cur.fetchall()[0][0]

        # Check: any unsent insights?
        cur.execute('''
            SELECT count(*) FROM insights WHERE reviewed = false
        ''')
        unsent = cur.fetchall()[0][0]

        print(f'Sent today: {sent_today}, WA activity: {wa_activity}, Unsent: {unsent}')

        # Logic:
        # - First batch of the day (sent_today == 0): always send
        # - Subsequent batches: only if Sebastian was active on WhatsApp since last send
        if sent_today > 0 and wa_activity <= sent_today:
            print('Waiting for Sebastian to respond before sending more.')
            sys.exit(0)

        if unsent == 0:
            print('No new insights to send.')
            sys.exit(0)

        # Get top 3 unsent, prioritize recommendations
        cur.execute('''
            SELECT id, insight_type, area, title, description, confidence
            FROM insights
            WHERE reviewed = false
            ORDER BY
                CASE WHEN insight_type = 'recommendation' THEN 0 ELSE 1 END,
                confidence DESC,
                created_at DESC
            LIMIT 3
        ''')
        rows = cur.fetchall()

for row in rows:
    iid, itype, area, title, desc, conf = row
    emoji = {'trading':'📈','business':'🏢','relationships':'👥','wellbeing':'💚','general':'🧠'}.get(area,'💡')
    type_label = {'recommendation':'Rekomendacja','pattern':'Wzorzec','observation':'Obserwacja','anomaly':'Anomalia'}.get(itype, itype)

    msg = f'{emoji} *{type_label}: {title}*\n\n{desc[:800]}\n\n_Pewność: {conf:.0%} | Obszar: {area}_\n\nOceń: 👍/👎 lub zadaj pytanie'

    result = subprocess.run(
        ['openclaw', 'message', 'send', '--channel', 'whatsapp',
         '--target', '+48505441635', '--message', msg],
        capture_output=True, text=True, timeout=30,
    )

    if result.returncode == 0:
        print(f'Sent: {title[:50]}')
        with get_pg_connection() as conn2:
            with conn2.cursor() as cur2:
                cur2.execute('UPDATE insights SET reviewed = true WHERE id = %s', (iid,))
            conn2.commit()
    else:
        print(f'Failed: {result.stderr[:100]}')
"
