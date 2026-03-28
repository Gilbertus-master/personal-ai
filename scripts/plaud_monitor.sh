#!/usr/bin/env bash
# plaud_monitor.sh — Full Plaud automation pipeline.
# Runs as cron every 15 minutes.
#
# Pipeline: Plaud Pin S → (Bluetooth/app sync) → Plaud Cloud → auto-trigger
#           transcription → poll for completion → import to Gilbertus →
#           embed → extract entities/events.
#
# The ONLY manual step is syncing Plaud Pin S with the phone app.
# Everything else is fully automatic.
set -euo pipefail

LOCKFILE=/tmp/plaud_monitor.lock
exec 9>"$LOCKFILE"
if ! flock -n 9; then
  LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE") ))
  if [ "$LOCK_AGE" -lt 2700 ]; then echo "[$(date '+%Y-%m-%d %H:%M')] plaud_monitor already running (${LOCK_AGE}s), skipping"; exit 0; fi
  echo "[$(date '+%Y-%m-%d %H:%M')] plaud_monitor stale lock (${LOCK_AGE}s), stealing"
fi
trap 'flock -u 9; rm -f $LOCKFILE' EXIT INT TERM

cd "$(dirname "$0")/.."

.venv/bin/python -c "
import requests, json, os, subprocess, sys, time
from datetime import datetime
from app.ingestion.plaud_sync import get_plaud_token, list_recordings, get_recording_details, sync_plaud

token = get_plaud_token()
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# --- Step 1: Scan all recordings (paginate through everything) ---
all_recs = []
skip = 0
while True:
    batch = list_recordings(token, limit=50, skip=skip)
    if not batch:
        break
    all_recs.extend(batch)
    if len(batch) < 50:
        break
    skip += len(batch)

now = datetime.now()

needs_transcription = []
transcribed = []

for r in all_recs:
    trans = r.get('is_trans', False)
    if trans:
        transcribed.append(r)
    else:
        needs_transcription.append(r)

print(f'[{now.strftime(\"%Y-%m-%d %H:%M\")}] Plaud: {len(all_recs)} total, {len(transcribed)} transcribed, {len(needs_transcription)} need transcription')

# --- Step 2: Auto-trigger transcription (2-step: PATCH config + POST trigger) ---
triggered = 0
for r in needs_transcription:
    fid = r['id']
    name = r.get('filename', '?')
    dur = r.get('duration', 0) / 1000
    # Skip very short recordings (<10s) — likely accidental
    if dur < 10:
        continue
    try:
        # Step 2a: Configure transcription via PATCH
        requests.patch(
            f'https://api.plaud.ai/file/{fid}',
            headers=headers,
            json={'extra_data': {'tranConfig': {'language': 'auto', 'trans_type': 1}}},
            timeout=15,
        )
        # Step 2b: Trigger transcription via POST
        resp = requests.post(
            f'https://api.plaud.ai/ai/transsumm/{fid}',
            headers={**headers, 'Origin': 'https://web.plaud.ai', 'Referer': 'https://web.plaud.ai/'},
            json={'language': 'auto', 'summ_type': 1, 'support_mul_summ': True,
                  'info': json.dumps({'language': 'auto', 'summary_type': 1})},
            timeout=30,
        )
        data = resp.json()
        if data.get('status') == 0 or 'processing' in str(data.get('msg', '')).lower():
            triggered += 1
            print(f'  Triggered transcription: {name} ({dur:.0f}s)')
        elif 'already' in str(data.get('msg', '')).lower():
            pass  # Already processing, skip
        else:
            msg = data.get('msg', '?')
            err = data.get('err_msg', '')
            status_code = data.get('status')
            print(f'  Trigger result {name}: status={status_code} msg={msg} err={err}')
    except Exception as e:
        print(f'  Error triggering {name}: {e}')

if triggered:
    print(f'  Triggered {triggered} new transcriptions')

# --- Step 2c: Fallback to local Whisper for any still-untranscribed ---
# Only run Whisper if no cloud transcriptions were triggered this cycle.
# If triggered > 0, cloud is actively processing — wait for next cycle.
if needs_transcription and not triggered:
    import subprocess, sys
    whisper_script = os.path.join(os.path.dirname(os.path.abspath('.')), 'personal-ai/app/ingestion/whisper_transcribe.py')
    whisper_script = 'app/ingestion/whisper_transcribe.py'
    print(f'  Running local Whisper fallback for {len(needs_transcription)} recordings...')
    result = subprocess.run(
        [sys.executable, whisper_script, str(len(needs_transcription))],
        capture_output=True, text=True, timeout=3600
    )
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0 and result.stderr:
        print(f'  Whisper error: {result.stderr[:200]}')

# --- Step 3: Import all transcribed recordings (paginate) ---
imported, chunks, skipped = sync_plaud(limit=50, sync_all=True)
if imported:
    print(f'  Imported {imported} recordings ({chunks} chunks)')

# --- Step 4: Embed + extract on new data ---
if imported:
    # Embed
    try:
        result = subprocess.run(
            ['.venv/bin/python', '-m', 'app.retrieval.index_chunks', '--batch-size', '100', '--limit', '500'],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, 'TIKTOKEN_CACHE_DIR': '/tmp/tiktoken_cache'},
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if 'indeksowano' in line.lower() or 'indexed' in line.lower():
                    print(f'  {line}')
    except Exception as e:
        print(f'  ERROR embed step: {e}', file=sys.stderr)

    # Extract entities
    try:
        subprocess.run(
            ['.venv/bin/python', '-m', 'app.extraction.entities', '--candidates-only', str(min(chunks * 3, 100))],
            capture_output=True, timeout=180,
            env={**os.environ, 'ANTHROPIC_EXTRACTION_MODEL': 'claude-haiku-4-5'},
        )
        print(f'  Extracted entities from audio data')
    except Exception as e:
        print(f'  ERROR entity extraction step: {e}', file=sys.stderr)

remaining = len(needs_transcription) - triggered
if remaining > 0:
    print(f'  Note: {remaining} recordings still awaiting transcription (processing or skipped)')
"
