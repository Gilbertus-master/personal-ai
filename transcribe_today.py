"""Download today's Plaud recordings and transcribe with local Whisper."""
import subprocess
import requests
from datetime import datetime
from app.ingestion.common.db import document_exists_by_raw_path, insert_chunk, insert_document, insert_source

PLAUD_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1MmM5NzcxODBhZjNjOTM1YmI0NjAzZjkxNmE5MjExYyIsImF1ZCI6IiIsImV4cCI6MTgwMDI1NDM3MywiaWF0IjoxNzc0MzM0MzczLCJjbGllbnRfaWQiOiJkZXNrdG9wIiwicmVnaW9uIjoiYXdzOnVzLXdlc3QtMiJ9.zO54PZRDc7VlSuaHaGQURK1qcLovb-WGW1BYDvkXoTQ"
PLAUD_API = "https://api.plaud.ai"
WHISPER_URL = "http://127.0.0.1:9090"
headers = {"Authorization": f"Bearer {PLAUD_TOKEN}"}

# 1. Get recordings from today (24 march)
r = requests.get(f"{PLAUD_API}/file/simple/web", headers=headers,
    params={"skip": 0, "limit": 50, "is_trash": 0, "sort_by": "start_time", "is_desc": "true"}, timeout=30)
recs = r.json().get("data_file_list", [])

# Filter: today's recordings, not transcribed, max 30 min (1800s)
today = []
for rec in recs:
    if rec.get("start_time", 0) <= 1.7743e12:
        continue
    if rec.get("is_trans"):
        continue
    dur = rec.get("duration", 0)
    if dur > 1000:
        dur = dur / 1000
    if dur > 7200:
        print(f"  Skip {rec.get('filename','?')}: too long ({dur:.0f}s)")
        continue
    today.append(rec)
print(f"Today's recordings to transcribe: {len(today)}")

source_id = insert_source(conn=None, source_type="audio_transcript", source_name="whisper_local")
imported = 0

for rec in today:
    fid = rec["id"]
    name = rec.get("filename", "?")
    dur = rec.get("duration", 0)
    if dur > 1000: dur = dur / 1000

    raw_path = f"plaud://whisper/{fid}"
    if document_exists_by_raw_path(raw_path):
        continue

    # Get audio URL
    try:
        resp = requests.get(f"{PLAUD_API}/file/temp-url/{fid}", headers=headers, timeout=15)
        audio_url = resp.json().get("temp_url")
        if not audio_url:
            print(f"  {name}: no audio URL")
            continue
    except Exception as e:
        print(f"  {name}: URL error {e}")
        continue

    # Download via Docker (bypass SSL)
    print(f"  Downloading {name} ({dur:.0f}s)...")
    dl = subprocess.run(
        ["docker", "exec", "gilbertus-whisper", "python", "-c",
         f"import urllib.request; urllib.request.urlretrieve('{audio_url}', '/audio/{fid}.mp3'); import os; print(os.path.getsize('/audio/{fid}.mp3'))"],
        capture_output=True, text=True, timeout=300)

    if dl.returncode != 0 or not dl.stdout.strip():
        print("    Download failed")
        continue
    print(f"    {int(dl.stdout.strip())/1024:.0f}KB")

    # Transcribe with Whisper
    print("    Transcribing...")
    with open(f"/tmp/whisper_audio/{fid}.mp3", "rb") as f:
        tr = requests.post(f"{WHISPER_URL}/transcribe", files={"file": f}, data={"language": "pl"}, timeout=600)

    # Clean up audio
    subprocess.run(["docker", "exec", "gilbertus-whisper", "rm", f"/audio/{fid}.mp3"], capture_output=True)

    if tr.status_code != 200:
        print(f"    Whisper failed: {tr.status_code}")
        continue

    result = tr.json()
    transcript = result.get("text", "")
    duration = result.get("duration", 0)
    segments = result.get("segments", [])
    print(f"    {len(transcript)} chars, {len(segments)} segments, {duration:.0f}s")

    if not transcript.strip():
        print("    Empty transcript")
        continue

    recorded_at = None
    st = rec.get("start_time", 0)
    if st > 1e12:
        recorded_at = datetime.fromtimestamp(st / 1000)

    lines = [f"Transkrypcja: {name}"]
    if recorded_at:
        lines.append(f"Data: {recorded_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Czas: {int(duration)}s")
    lines.append("")
    for seg in segments:
        lines.append(f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")
    full_text = "\n".join(lines)

    doc_id = insert_document(conn=None, source_id=source_id, title=name,
        created_at=recorded_at, author=None, participants=[], raw_path=raw_path)

    chunks = []
    start = 0
    while start < len(full_text):
        end = min(start + 3000, len(full_text))
        chunk = full_text[start:end].strip()
        if chunk: chunks.append(chunk)
        if end >= len(full_text): break
        start = max(end - 300, start + 1)

    for ci, chunk in enumerate(chunks):
        insert_chunk(conn=None, document_id=doc_id, chunk_index=ci, text=chunk,
            timestamp_start=recorded_at, timestamp_end=recorded_at, embedding_id=None)

    imported += 1
    print(f"    OK: {len(chunks)} chunks")

print(f"\nDone: {imported} recordings transcribed and imported")
