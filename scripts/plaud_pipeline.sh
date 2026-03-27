#!/usr/bin/env bash
# plaud_pipeline.sh — Robust Plaud → Whisper → DB pipeline
# Strategy:
#   1. Scan all untranscribed recordings
#   2. Try Plaud cloud transcription trigger
#   3. Fallback: download from S3 temp-url via curl, transcribe with local Whisper
#   4. Import all newly transcribed (Plaud or Whisper)
#   5. Skip recordings with partial audio (<30s) — retry on next cron run

set -euo pipefail
cd "$(dirname "$0")/.."
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M')] plaud_pipeline"

VENV_PYTHON=".venv/bin/python3"
WHISPER_URL="http://127.0.0.1:9090"
MIN_AUDIO_SECONDS=30
PLAUD_API="https://api.plaud.ai"

echo "$LOG_PREFIX: starting"

$VENV_PYTHON - << 'PYEOF'
import sys, os, requests, json, subprocess, tempfile, time
sys.path.insert(0, '/home/sebastian/personal-ai')

from app.ingestion.plaud_sync import get_plaud_token, list_recordings, sync_plaud
from app.ingestion.common.db import document_exists_by_raw_path, insert_chunk, insert_document, insert_source
from app.utils.network import ensure_wsl2_mtu

ensure_wsl2_mtu()

WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:9090")
PLAUD_API = "https://api.plaud.ai"
MIN_AUDIO_SECONDS = 30

token = get_plaud_token()
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# Step 1: Get all recordings
all_recs = []
skip = 0
while True:
    batch = list_recordings(token, limit=50, skip=skip)
    if not batch: break
    all_recs.extend(batch)
    if len(batch) < 50: break
    skip += len(batch)

needs = [r for r in all_recs if not r.get("is_trans") and r.get("duration", 0)/1000 > 10]
print(f"Untranscribed: {len(needs)} / {len(all_recs)}")

# Step 2: Try Plaud cloud trigger
triggered = 0
for r in needs:
    fid = r["id"]
    fname = r.get("filename", "?")
    try:
        requests.patch(f"{PLAUD_API}/file/{fid}", headers=headers,
            json={"extra_data": {"tranConfig": {"language": "auto", "trans_type": 1}}}, timeout=15)
        resp = requests.post(f"{PLAUD_API}/ai/transsumm/{fid}",
            headers={**headers, "Origin": "https://web.plaud.ai", "Referer": "https://web.plaud.ai/"},
            json={"language": "auto", "summ_type": "1", "support_mul_summ": True,
                  "info": json.dumps({"language": "auto", "summary_type": 1})}, timeout=30)
        status_code = resp.json().get("status")
        if status_code == 0:
            triggered += 1
            print(f"  Plaud triggered: {fname}")
    except Exception as e:
        pass  # Will fall through to Whisper

if triggered:
    print(f"  Waiting 30s for Plaud to process...")
    time.sleep(30)

# Step 3: Whisper fallback for still-untranscribed
source_id = insert_source(conn=None, source_type="audio_transcript", source_name="whisper_local")
whisper_imported = 0

for r in needs:
    fid = r["id"]
    fname = r.get("filename", "?")
    fullname = (r.get("fullname") or r.get("id", "")).rsplit(".", 1)[0]
    raw_path = f"plaud://whisper/{fid}"

    if document_exists_by_raw_path(raw_path):
        continue

    # Get S3 URL
    try:
        url_resp = requests.get(f"{PLAUD_API}/file/temp-url/{fullname}",
            headers={"Authorization": f"Bearer {token}"}, timeout=15, verify=False)
        audio_url = url_resp.json().get("temp_url")
    except Exception:
        audio_url = None

    if not audio_url:
        print(f"  Skip (no S3 URL): {fname}")
        continue

    # Download via curl (SSL-safe)
    tmp_audio = f"/tmp/plaud_{fid[:12]}.mp3"
    try:
        result = subprocess.run(
            ["curl", "-k", "-L", "-s", "-o", tmp_audio, "--max-time", "120", audio_url],
            timeout=130, capture_output=True
        )
        if result.returncode != 0 or not os.path.exists(tmp_audio):
            print(f"  Skip (download failed): {fname}")
            continue
        size = os.path.getsize(tmp_audio)
        if size < 10000:
            print(f"  Skip (file too small {size}B, not ready): {fname}")
            os.unlink(tmp_audio)
            continue
    except Exception as e:
        print(f"  Skip (curl error): {fname}: {e}")
        continue

    # Send to Whisper
    try:
        with open(tmp_audio, "rb") as f:
            w_resp = requests.post(f"{WHISPER_URL}/transcribe",
                files={"file": f}, data={"language": "pl"}, timeout=600)
        w_resp.raise_for_status()
        result_data = w_resp.json()
        transcript = result_data.get("text", "")
        duration = result_data.get("duration", 0)
        segments = result_data.get("segments", [])
        os.unlink(tmp_audio)
    except Exception as e:
        print(f"  Skip (Whisper error): {fname}: {e}")
        if os.path.exists(tmp_audio): os.unlink(tmp_audio)
        continue

    if duration < MIN_AUDIO_SECONDS:
        print(f"  Skip (only {duration:.0f}s transcribed, audio not fully uploaded): {fname}")
        continue

    if not transcript.strip():
        print(f"  Skip (empty transcript): {fname}")
        continue

    # Parse timestamp
    from datetime import datetime
    recorded_at = None
    start_time = r.get("start_time", 0)
    if start_time:
        ts = start_time / 1000 if start_time > 1e12 else start_time
        try: recorded_at = datetime.fromtimestamp(ts)
        except: pass

    # Build full text with timestamps
    lines = [f"Transkrypcja (Whisper): {fname}", f"Czas trwania: {int(duration)}s", ""]
    for seg in segments:
        lines.append(f"[{seg['start']:.1f}s] {seg['text']}")
    full_text = "\n".join(lines)

    # Import to DB
    def chunk_text(text, target=3000, overlap=300):
        chunks, start = [], 0
        while start < len(text):
            end = min(start + target, len(text))
            chunk = text[start:end].strip()
            if chunk: chunks.append(chunk)
            if end >= len(text): break
            start = max(end - overlap, start + 1)
        return chunks or [""]

    doc_id = insert_document(conn=None, source_id=source_id, title=fname,
        created_at=recorded_at, author=None, participants=[], raw_path=raw_path)

    chunks = chunk_text(full_text)
    for ci, chunk in enumerate(chunks):
        insert_chunk(conn=None, document_id=doc_id, chunk_index=ci, text=chunk,
            timestamp_start=recorded_at, timestamp_end=recorded_at, embedding_id=None)

    whisper_imported += 1
    print(f"  Whisper imported: {fname} ({duration:.0f}s, {len(chunks)} chunks)")

# Step 4: Import Plaud-transcribed recordings
imported, chunks_total, _ = sync_plaud(limit=50, sync_all=True)
print(f"\nSummary: Plaud imported={imported}, Whisper imported={whisper_imported}, chunks={chunks_total}")
PYEOF
