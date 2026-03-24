#!/usr/bin/env bash
# plaud_monitor.sh — Monitors Plaud recordings, auto-triggers transcription, auto-imports.
# Runs as cron every 15 minutes.
set -euo pipefail
cd "$(dirname "$0")/.."

.venv/bin/python -c "
import requests, json
from datetime import datetime
from app.ingestion.plaud_sync import get_plaud_token, list_recordings, get_recording_details, sync_plaud

token = get_plaud_token()
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

recs = list_recordings(token, limit=50)
now = datetime.now()

uploaded_no_trans = []
not_uploaded = []
transcribed = []

for r in recs:
    ori = r.get('ori_ready', False)
    trans = r.get('is_trans', False)
    start = r.get('start_time', 0)

    if trans:
        transcribed.append(r)
    elif ori and not trans:
        uploaded_no_trans.append(r)
    else:
        not_uploaded.append(r)

print(f'[{now.strftime(\"%Y-%m-%d %H:%M\")}] Plaud status: {len(transcribed)} transcribed, {len(uploaded_no_trans)} uploaded (no trans), {len(not_uploaded)} not uploaded')

# Auto-trigger transcription for uploaded recordings
triggered = 0
for r in uploaded_no_trans:
    fid = r['id']
    name = r.get('filename', '?')
    try:
        resp = requests.post(
            f'https://api.plaud.ai/ai/transsumm/{fid}',
            headers=headers,
            json={'language': 'auto'},
            timeout=30,
        )
        data = resp.json()
        if data.get('status') == 0:
            triggered += 1
            print(f'  Triggered transcription: {name}')
        else:
            print(f'  Failed to trigger {name}: {data.get(\"msg\", \"?\")}')
    except Exception as e:
        print(f'  Error triggering {name}: {e}')

if triggered:
    print(f'  Triggered {triggered} transcriptions')

# Auto-import newly transcribed recordings
imported, chunks, skipped = sync_plaud(limit=50)
if imported:
    print(f'  Imported {imported} recordings ({chunks} chunks)')

# Index new chunks
if imported:
    import subprocess
    result = subprocess.run(
        ['.venv/bin/python', '-m', 'app.retrieval.index_chunks', '--batch-size', '100', '--limit', '200'],
        capture_output=True, text=True, timeout=120,
        env={**__import__('os').environ, 'TIKTOKEN_CACHE_DIR': '/tmp/tiktoken_cache'},
    )
    if 'Zaindeksowano' in result.stdout:
        print(f'  {result.stdout.strip().splitlines()[-1]}')
"
