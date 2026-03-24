#!/usr/bin/env bash
# continuous_improvement.sh — Runs every 2 hours. Autonomous improvement loop.
set -euo pipefail
cd "$(dirname "$0")/.."

LOG="logs/continuous_improvement.log"
echo "[$(date '+%F %T')] === Continuous improvement cycle starting ===" >> "$LOG"

# 1. Entity extraction (push toward 20%)
echo "[$(date '+%F %T')] Entity extraction (200 chunks)" >> "$LOG"
ANTHROPIC_EXTRACTION_MODEL=claude-haiku-4-5-20251001 \
    .venv/bin/python -m app.extraction.entities --candidates-only 200 >> "$LOG" 2>&1 || true

# 2. Event extraction (process candidates)
echo "[$(date '+%F %T')] Event extraction (100 chunks)" >> "$LOG"
ANTHROPIC_EXTRACTION_MODEL=claude-haiku-4-5-20251001 \
    .venv/bin/python -m app.extraction.events --candidates-only 100 >> "$LOG" 2>&1 || true

# 3. Generate insights from new data
echo "[$(date '+%F %T')] Generating new insights" >> "$LOG"
.venv/bin/python -c "
from app.db.postgres import get_pg_connection
from datetime import datetime, timedelta
import json

now = datetime.now()
week_ago = now - timedelta(days=7)

with get_pg_connection() as conn:
    with conn.cursor() as cur:
        # Find new patterns in recent data
        
        # A) Most active entities this week
        cur.execute('''
            SELECT en.canonical_name, en.entity_type, count(*) as mentions
            FROM chunk_entities ce
            JOIN entities en ON en.id = ce.entity_id
            JOIN chunks c ON c.id = ce.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE d.created_at >= %s
            GROUP BY en.id, en.canonical_name, en.entity_type
            ORDER BY count(*) DESC LIMIT 5
        ''', (week_ago,))
        recent_entities = cur.fetchall()
        
        if recent_entities:
            names = ', '.join([f'{r[0]} ({r[2]})' for r in recent_entities])
            cur.execute('''
                INSERT INTO insights (insight_type, area, title, description, evidence, confidence)
                SELECT 'observation', 'general', 
                    'Najaktywniejsze encje w ostatnim tygodniu',
                    %s, %s, 0.8
                WHERE NOT EXISTS (
                    SELECT 1 FROM insights WHERE title = 'Najaktywniejsze encje w ostatnim tygodniu'
                    AND created_at > NOW() - INTERVAL '24 hours'
                )
            ''', (
                f'W ostatnim tygodniu najczęściej pojawiały się: {names}',
                f'Dane z {len(recent_entities)} encji, okres {week_ago.date()} - {now.date()}'
            ))
        
        # B) Event type distribution this month
        cur.execute('''
            SELECT event_type, count(*) 
            FROM events WHERE created_at >= NOW() - INTERVAL '30 days'
            GROUP BY event_type ORDER BY count(*) DESC
        ''')
        recent_events = cur.fetchall()
        
        if recent_events:
            dist = ', '.join([f'{r[0]}: {r[1]}' for r in recent_events])
            cur.execute('''
                INSERT INTO insights (insight_type, area, title, description, evidence, confidence)
                SELECT 'pattern', 'general',
                    'Rozkład typów wydarzeń (ostatnie 30 dni)',
                    %s, %s, 0.9
                WHERE NOT EXISTS (
                    SELECT 1 FROM insights WHERE title = 'Rozkład typów wydarzeń (ostatnie 30 dni)'
                    AND created_at > NOW() - INTERVAL '24 hours'
                )
            ''', (
                f'W ostatnich 30 dniach wykryte wydarzenia: {dist}',
                f'{sum(r[1] for r in recent_events)} wydarzeń łącznie'
            ))
        
    conn.commit()
    
print('Insights check done')
" >> "$LOG" 2>&1 || true

# 4. Import new data from all live sources
echo "[$(date '+%F %T')] Live ingest" >> "$LOG"
.venv/bin/python -m app.ingestion.live_ingest >> "$LOG" 2>&1 || true

# 5. Plaud sync
echo "[$(date '+%F %T')] Plaud sync" >> "$LOG"
.venv/bin/python -m app.ingestion.plaud_sync 50 >> "$LOG" 2>&1 || true

# 6. Embed any new chunks
echo "[$(date '+%F %T')] Embedding" >> "$LOG"
TIKTOKEN_CACHE_DIR=/tmp/tiktoken_cache \
    .venv/bin/python -m app.retrieval.index_chunks --batch-size 100 --limit 500 >> "$LOG" 2>&1 || true

# 7. Run alerts check
echo "[$(date '+%F %T')] Alerts check" >> "$LOG"
.venv/bin/python -m app.retrieval.alerts >> "$LOG" 2>&1 || true

echo "[$(date '+%F %T')] === Cycle complete ===" >> "$LOG"
