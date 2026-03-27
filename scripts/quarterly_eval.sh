#!/usr/bin/env bash
# quarterly_eval.sh — Auto-generate evaluations for all active business contacts.
# Cron: 0 8 1 1,4,7,10 * (first day of each quarter at 8:00)
set -uo pipefail
cd "$(dirname "$0")/.."

LOG="logs/quarterly_eval_$(date +%Y%m%d).log"
echo "[$(date '+%H:%M:%S')] Quarterly evaluation started" | tee "$LOG"

# Get all active business people
PEOPLE=$(.venv/bin/python -c "
from app.db.postgres import get_pg_connection
with get_pg_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(\"\"\"
            SELECT p.first_name || '-' || p.last_name as slug
            FROM people p
            JOIN relationships r ON r.person_id = p.id
            WHERE r.status = 'active' AND r.relationship_type = 'business'
        \"\"\")
        for row in cur.fetchall():
            print(row[0].lower())
")

# Date range: last quarter
QUARTER_END=$(date +%Y-%m-01)
QUARTER_START=$(date -d "$QUARTER_END - 3 months" +%Y-%m-%d)

echo "[$(date '+%H:%M:%S')] Period: $QUARTER_START to $QUARTER_END" | tee -a "$LOG"

for slug in $PEOPLE; do
    echo "[$(date '+%H:%M:%S')] Evaluating: $slug" | tee -a "$LOG"
    .venv/bin/python -c "
from app.evaluation.data_collector import collect_person_data
from app.evaluation.evaluator import evaluate_person
import json

data = collect_person_data(person_slug='$slug', date_from='$QUARTER_START', date_to='$QUARTER_END')
if 'error' not in data:
    result = evaluate_person(data)
    score = result.get('evaluation', {}).get('overall_score', '?')
    print(f'  Score: {score}, Confidence: {result.get(\"confidence\", \"?\")}')
else:
    print(f'  Error: {data[\"error\"]}')
" >> "$LOG" 2>&1 || echo "  FAILED" | tee -a "$LOG"
done

echo "[$(date '+%H:%M:%S')] Quarterly evaluation done" | tee -a "$LOG"
