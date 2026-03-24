#!/usr/bin/env bash
# continuous_improvement.sh — Runs every 2 hours. Deep analysis across FULL history.
set -euo pipefail
cd "$(dirname "$0")/.."

LOG="logs/continuous_improvement.log"
TS() { date '+%F %T'; }

echo "[$(TS)] === Continuous improvement cycle ===" >> "$LOG"

# 1. AGGRESSIVE entity extraction (500 per cycle)
echo "[$(TS)] Entity extraction (500)" >> "$LOG"
ANTHROPIC_EXTRACTION_MODEL=claude-haiku-4-5-20251001 \
    .venv/bin/python -m app.extraction.entities --candidates-only 500 >> "$LOG" 2>&1 || true

# 2. AGGRESSIVE event extraction (500 per cycle)
echo "[$(TS)] Event extraction (500)" >> "$LOG"
ANTHROPIC_EXTRACTION_MODEL=claude-haiku-4-5-20251001 \
    .venv/bin/python -m app.extraction.events --candidates-only 500 >> "$LOG" 2>&1 || true

# 3. DEEP INSIGHTS from FULL HISTORY (not just recent data)
echo "[$(TS)] Deep insight analysis (full history)" >> "$LOG"
.venv/bin/python -c "
from app.db.postgres import get_pg_connection
from collections import defaultdict

with get_pg_connection() as conn:
    with conn.cursor() as cur:

        # A) Long-term entities (appear across 6+ months of full history)
        cur.execute('''
            SELECT en.canonical_name, en.entity_type,
                   MIN(d.created_at)::date as first_seen,
                   MAX(d.created_at)::date as last_seen,
                   count(DISTINCT date_trunc(''month'', d.created_at)) as active_months,
                   count(*) as total_mentions
            FROM chunk_entities ce
            JOIN entities en ON en.id = ce.entity_id
            JOIN chunks c ON c.id = ce.chunk_id
            JOIN documents d ON d.id = c.document_id
            WHERE d.created_at IS NOT NULL
            GROUP BY en.id, en.canonical_name, en.entity_type
            HAVING count(DISTINCT date_trunc(''month'', d.created_at)) >= 6
            ORDER BY count(*) DESC LIMIT 10
        ''')
        for r in cur.fetchall():
            name, etype, first, last, months, mentions = r
            area = {'person':'relationships','company':'business'}.get(etype,'general')
            cur.execute('''
                INSERT INTO insights (insight_type, area, title, description, evidence, confidence)
                SELECT 'pattern', %s, %s, %s, %s, 0.85
                WHERE NOT EXISTS (
                    SELECT 1 FROM insights WHERE title = %s AND created_at > NOW() - INTERVAL '7 days'
                )
            ''', (area,
                f'Kluczowa encja: {name}',
                f'{name} ({etype}) obecny w danych od {first} do {last} ({months} aktywnych miesięcy, {mentions} wzmianek). Jedna z najważniejszych encji w pełnej historii.',
                f'span={first}-{last}, months={months}, mentions={mentions}',
                f'Kluczowa encja: {name}'))

        # B) Relationship co-occurrence (full history)
        cur.execute('''
            SELECT e1.canonical_name, e2.canonical_name, count(*) as co
            FROM chunk_entities ce1
            JOIN chunk_entities ce2 ON ce1.chunk_id = ce2.chunk_id AND ce1.entity_id < ce2.entity_id
            JOIN entities e1 ON e1.id = ce1.entity_id
            JOIN entities e2 ON e2.id = ce2.entity_id
            WHERE e1.entity_type = 'person' AND e2.entity_type = 'person'
            GROUP BY e1.canonical_name, e2.canonical_name
            HAVING count(*) >= 10
            ORDER BY count(*) DESC LIMIT 10
        ''')
        pairs = cur.fetchall()
        if pairs:
            desc = '; '.join([f'{r[0]}↔{r[1]} ({r[2]}x)' for r in pairs[:5]])
            cur.execute('''
                INSERT INTO insights (insight_type, area, title, description, evidence, confidence)
                SELECT 'pattern', 'relationships',
                    'Najsilniejsze powiązania osób (pełna historia)', %s, %s, 0.8
                WHERE NOT EXISTS (
                    SELECT 1 FROM insights WHERE title = 'Najsilniejsze powiązania osób (pełna historia)'
                    AND created_at > NOW() - INTERVAL '7 days'
                )
            ''', (f'Pary najczęściej współwystępujące w CAŁEJ historii danych: {desc}',
                  f'{len(pairs)} par'))

        # C) Event trajectory (full history, quarterly)
        cur.execute('''
            SELECT date_trunc(''quarter'', event_time)::date as q, event_type, count(*)
            FROM events WHERE event_time IS NOT NULL
            GROUP BY q, event_type ORDER BY q
        ''')
        by_type = defaultdict(list)
        for q, etype, cnt in cur.fetchall():
            by_type[etype].append((q, cnt))

        for etype, points in by_type.items():
            if len(points) >= 4:
                first_half = sum(p[1] for p in points[:len(points)//2])
                second_half = sum(p[1] for p in points[len(points)//2:])
                if second_half > first_half * 1.5:
                    trend = 'rosnący'
                elif second_half < first_half * 0.5:
                    trend = 'malejący'
                else:
                    continue
                pct = round(100*(second_half-first_half)/max(first_half,1))
                cur.execute('''
                    INSERT INTO insights (insight_type, area, title, description, evidence, confidence)
                    SELECT 'pattern', 'general', %s, %s, %s, 0.75
                    WHERE NOT EXISTS (
                        SELECT 1 FROM insights WHERE title = %s AND created_at > NOW() - INTERVAL '7 days'
                    )
                ''', (f'Trend {trend}: {etype}',
                      f'Wydarzenia {etype} w pełnej historii wykazują trend {trend} ({pct:+d}%). Pierwsza połowa: {first_half}, druga: {second_half}.',
                      f'quarters={len(points)}',
                      f'Trend {trend}: {etype}'))

        # D) Source-cross patterns: topics appearing across multiple source types
        cur.execute('''
            SELECT en.canonical_name, en.entity_type,
                   array_agg(DISTINCT s.source_type) as sources,
                   count(DISTINCT s.source_type) as source_count
            FROM chunk_entities ce
            JOIN entities en ON en.id = ce.entity_id
            JOIN chunks c ON c.id = ce.chunk_id
            JOIN documents d ON d.id = c.document_id
            JOIN sources s ON d.source_id = s.id
            GROUP BY en.id, en.canonical_name, en.entity_type
            HAVING count(DISTINCT s.source_type) >= 4
            ORDER BY count(DISTINCT s.source_type) DESC, count(*) DESC LIMIT 10
        ''')
        cross_source = cur.fetchall()
        if cross_source:
            for r in cross_source[:5]:
                name, etype, sources, cnt = r
                cur.execute('''
                    INSERT INTO insights (insight_type, area, title, description, evidence, confidence)
                    SELECT 'observation', 'general', %s, %s, %s, 0.9
                    WHERE NOT EXISTS (
                        SELECT 1 FROM insights WHERE title = %s AND created_at > NOW() - INTERVAL '7 days'
                    )
                ''', (f'Cross-source: {name}',
                      f'{name} pojawia się w {cnt} różnych typach źródeł: {sources}. To oznacza że ta encja przenika wiele obszarów życia Sebastiana.',
                      f'sources={sources}, count={cnt}',
                      f'Cross-source: {name}'))

    conn.commit()
print('Deep full-history insights done')
" >> "$LOG" 2>&1 || true

# 4. Import + embed + alerts
echo "[$(TS)] Live ingest + Plaud + embed + alerts" >> "$LOG"
.venv/bin/python -m app.ingestion.live_ingest >> "$LOG" 2>&1 || true
.venv/bin/python -m app.ingestion.plaud_sync 50 >> "$LOG" 2>&1 || true
TIKTOKEN_CACHE_DIR=/tmp/tiktoken_cache .venv/bin/python -m app.retrieval.index_chunks --batch-size 100 --limit 1000 >> "$LOG" 2>&1 || true
.venv/bin/python -m app.retrieval.alerts >> "$LOG" 2>&1 || true

echo "[$(TS)] === Cycle complete ===" >> "$LOG"
