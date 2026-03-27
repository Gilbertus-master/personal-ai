#!/usr/bin/env bash
# decision_reminders.sh — Remind Sebastian to check decision outcomes.
# Sends WhatsApp reminders at 7, 30, 90 days after decision.
# Cron: 0 8 * * * (daily at 8:00 CET)
set -uo pipefail
cd "$(dirname "$0")/.."

.venv/bin/python -c "
from app.db.postgres import get_pg_connection
import subprocess, json

OPENCLAW_BIN = 'openclaw'
TARGET = '+48505441635'

def send_wa(msg):
    try:
        subprocess.run([OPENCLAW_BIN, 'message', 'send', '--channel', 'whatsapp',
                       '--target', TARGET, '--message', msg],
                      capture_output=True, text=True, timeout=30)
    except Exception:
        print(f'WhatsApp send failed: {msg[:50]}')

with get_pg_connection() as conn:
    with conn.cursor() as cur:
        # 7-day reminders
        cur.execute('''
            SELECT id, decision_text, area, decided_at
            FROM decisions
            WHERE decided_at < NOW() - INTERVAL '7 days'
              AND reminder_sent_7d = FALSE
        ''')
        for row in cur.fetchall():
            did, text, area, date = row
            send_wa(f'📋 *Reminder: Decyzja #{did} (7 dni)*\nObszar: {area}\n{text[:200]}\n\nCzy znasz juz wynik? Odpowiedz: outcome #{did}: [opis wyniku]')
            cur.execute('UPDATE decisions SET reminder_sent_7d = TRUE WHERE id = %s', (did,))
            print(f'  7d reminder: #{did}')

        # 30-day reminders
        cur.execute('''
            SELECT id, decision_text, area, decided_at
            FROM decisions
            WHERE decided_at < NOW() - INTERVAL '30 days'
              AND reminder_sent_30d = FALSE
        ''')
        for row in cur.fetchall():
            did, text, area, date = row
            send_wa(f'📋 *Reminder: Decyzja #{did} (30 dni)*\nObszar: {area}\n{text[:200]}\n\nMinal miesiac. Jaki jest wynik?')
            cur.execute('UPDATE decisions SET reminder_sent_30d = TRUE WHERE id = %s', (did,))
            print(f'  30d reminder: #{did}')

        # 90-day reminders
        cur.execute('''
            SELECT id, decision_text, area, decided_at
            FROM decisions
            WHERE decided_at < NOW() - INTERVAL '90 days'
              AND reminder_sent_90d = FALSE
        ''')
        for row in cur.fetchall():
            did, text, area, date = row
            send_wa(f'📋 *Reminder: Decyzja #{did} (90 dni)*\nObszar: {area}\n{text[:200]}\n\nMinelo 3 miesiace. Ostateczna ocena wyniku?')
            cur.execute('UPDATE decisions SET reminder_sent_90d = TRUE WHERE id = %s', (did,))
            print(f'  90d reminder: #{did}')

    conn.commit()
print('Decision reminders done.')
" 2>&1
