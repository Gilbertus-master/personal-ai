"""
Backfill weekly summaries for 'general' area from 2025-01 to 2026-03.
Runs every 4th week to reduce API costs.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from app.retrieval.summaries import generate_weekly_summaries

start = datetime(2025, 1, 6)  # First Monday of 2025
end = datetime(2026, 3, 17)

current = start
week_num = 0
total_generated = 0
total_skipped = 0
total_errors = 0

while current < end:
    week_str = current.strftime('%Y-%m-%d')

    # Every 4th week to reduce API costs
    if week_num % 4 == 0:
        print(f'[{week_num:3d}] Generating: {week_str}', flush=True)
        try:
            results = generate_weekly_summaries(week_str, areas=['general'])
            for r in results:
                status = r.get('status', 'unknown')
                print(f'       {r.get("area", "general")}: {status}', flush=True)
                if status in ('generated', 'exists'):
                    total_generated += 1
                else:
                    total_skipped += 1
            # Small delay to avoid rate limiting
            time.sleep(1)
        except Exception as e:
            print(f'       ERROR: {e}', flush=True)
            total_errors += 1
            time.sleep(2)
    else:
        total_skipped += 1

    current += timedelta(weeks=1)
    week_num += 1

print(f'\nDone. Generated: {total_generated}, Skipped: {total_skipped}, Errors: {total_errors}')
