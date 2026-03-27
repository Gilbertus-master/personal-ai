"""
Local transcription pipeline: downloads audio from Plaud → transcribes with self-hosted Whisper.

Replaces dependency on Plaud cloud transcription.
Works for recordings where Plaud hasn't transcribed (is_trans=False) but audio is uploaded (ori_ready=True).
Also works with local audio files.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

import requests
from dotenv import load_dotenv

from app.utils.network import ssl_safe_download
from app.ingestion.common.db import (
    document_exists_by_raw_path,
    insert_chunk,
    insert_document,
    insert_source,
)
from app.ingestion.plaud_sync import get_plaud_token, list_recordings

load_dotenv()

WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:9090")
PLAUD_API = "https://api.plaud.ai"

CHUNK_TARGET_CHARS = 3000
CHUNK_OVERLAP_CHARS = 300


def transcribe_audio(audio_path: str, language: str = "pl") -> dict[str, Any]:
    """Send audio file to local Whisper server and get transcription."""
    with open(audio_path, "rb") as f:
        resp = requests.post(
            f"{WHISPER_URL}/transcribe",
            files={"file": f},
            data={"language": language},
            timeout=600,  # Long timeout for large files
        )
    resp.raise_for_status()
    return resp.json()


def get_plaud_audio_url(token: str, rec: dict) -> str | None:
    """Get presigned S3 download URL for Plaud recording audio.

    Plaud uses two IDs:
    - rec['id']       = short 20-char ID  (used in list, trigger)
    - rec['fullname'] = long MD5 filename  (used for /file/temp-url)

    The /file/temp-url endpoint requires the fullname (without extension).
    """
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    # Derive long file ID from fullname (strip extension)
    fullname = rec.get("fullname") or rec.get("ori_fullname") or rec.get("id", "")
    long_id = fullname.rsplit(".", 1)[0] if "." in fullname else fullname

    # Fall back to short id if no fullname
    ids_to_try = [long_id, rec.get("id", "")]
    for file_id in ids_to_try:
        if not file_id:
            continue
        try:
            resp = requests.get(
                f"{PLAUD_API}/file/temp-url/{file_id}",
                headers=headers,
                timeout=30,
                verify=False,
            )
            data = resp.json()
            url = data.get("temp_url")
            if url:
                return url
        except Exception as e:
            print(f"  temp-url error for {file_id}: {e}")

    print(f"  No audio URL found for {rec.get('filename','?')}")
    return None


def download_audio(url: str, suffix: str = ".opus") -> str:
    """Download audio file to temp path, using SSL-safe download for WSL2 resilience."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()
    ssl_safe_download(url, tmp.name, timeout=180)
    return tmp.name


def chunk_text(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return [""]
    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + CHUNK_TARGET_CHARS, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - CHUNK_OVERLAP_CHARS, start + 1)
    return chunks


def transcribe_plaud_recordings(limit: int = 10) -> tuple[int, int]:
    """Find Plaud recordings with no transcription, transcribe locally via Whisper."""
    token = get_plaud_token()

    # Paginate all recordings
    recs: list = []
    skip = 0
    while True:
        batch = list_recordings(token, limit=50, skip=skip)
        if not batch:
            break
        recs.extend(batch)
        if len(batch) < 50:
            break
        skip += len(batch)

    # Filter: not yet transcribed and not already imported (check DB by plaud://whisper/ path)
    candidates = [r for r in recs if not r.get("is_trans")]
    print(f"Recordings without transcription: {len(candidates)} / {len(recs)} total")
    candidates = candidates[:limit]
    source_id = insert_source(conn=None, source_type="audio_transcript", source_name="whisper_local")

    imported = 0
    chunks_total = 0

    for rec in candidates:
        file_id = rec.get("id", "")
        name = rec.get("filename", "?")
        raw_path = f"plaud://whisper/{file_id}"

        if document_exists_by_raw_path(raw_path):
            continue

        print(f"  Processing: {name}")

        # Get audio URL (pass full rec dict for ID resolution)
        audio_url = get_plaud_audio_url(token, rec)
        if not audio_url:
            print("    Skip: no audio URL")
            continue

        # Download audio
        try:
            audio_path = download_audio(audio_url)
            print(f"    Downloaded audio ({os.path.getsize(audio_path)} bytes)")
        except Exception as e:
            print(f"    Skip: download failed: {e}")
            continue

        # Transcribe with local Whisper
        try:
            result = transcribe_audio(audio_path)
            transcript = result.get("text", "")
            duration = result.get("duration", 0)
            segments = result.get("segments", [])
            print(f"    Transcribed: {len(transcript)} chars, {len(segments)} segments, {duration:.0f}s")
        except Exception as e:
            print(f"    Skip: transcription failed: {e}")
            os.unlink(audio_path)
            continue
        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

        if not transcript.strip():
            print("    Skip: empty transcript")
            continue

        # Parse timestamp
        recorded_at = None
        start_time = rec.get("start_time", 0)
        if start_time:
            try:
                ts = start_time / 1000 if start_time > 1e12 else start_time
                recorded_at = datetime.fromtimestamp(ts)
            except (ValueError, TypeError, OSError):
                pass

        # Build text with segments
        lines = [f"Transkrypcja (Whisper): {name}"]
        if recorded_at:
            lines.append(f"Data: {recorded_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Czas trwania: {int(duration)}s")
        lines.append("")

        if segments:
            for seg in segments:
                ts = f"[{seg['start']:.1f}-{seg['end']:.1f}]"
                lines.append(f"{ts} {seg['text']}")
        else:
            lines.append(transcript)

        full_text = "\n".join(lines)

        # Import
        document_id = insert_document(
            conn=None,
            source_id=source_id,
            title=name,
            created_at=recorded_at,
            author=None,
            participants=[],
            raw_path=raw_path,
        )

        chunks = chunk_text(full_text)
        for chunk_index, chunk in enumerate(chunks):
            insert_chunk(
                conn=None,
                document_id=document_id,
                chunk_index=chunk_index,
                text=chunk,
                timestamp_start=recorded_at,
                timestamp_end=recorded_at,
                embedding_id=None,
            )

        imported += 1
        chunks_total += len(chunks)
        print(f"    Imported: {len(chunks)} chunks")

    print(f"Done: {imported} transcribed and imported, {chunks_total} chunks")
    return imported, chunks_total


def transcribe_local_file(audio_path: str, language: str = "pl") -> None:
    """Transcribe a local audio file and import to Gilbertus."""
    print(f"Transcribing: {audio_path}")
    result = transcribe_audio(audio_path, language)
    transcript = result.get("text", "")
    duration = result.get("duration", 0)
    segments = result.get("segments", [])
    print(f"Result: {len(transcript)} chars, {len(segments)} segments, {duration:.0f}s")

    if not transcript.strip():
        print("Empty transcript")
        return

    from pathlib import Path
    name = Path(audio_path).stem

    source_id = insert_source(conn=None, source_type="audio_transcript", source_name="whisper_local")
    raw_path = f"whisper://local/{name}"

    lines = [f"Transkrypcja (Whisper): {name}"]
    lines.append(f"Czas trwania: {int(duration)}s")
    lines.append("")
    for seg in segments:
        lines.append(f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")
    full_text = "\n".join(lines)

    document_id = insert_document(
        conn=None,
        source_id=source_id,
        title=name,
        created_at=datetime.now(tz=timezone.utc),
        author=None,
        participants=[],
        raw_path=raw_path,
    )

    chunks = chunk_text(full_text)
    for chunk_index, chunk in enumerate(chunks):
        insert_chunk(
            conn=None,
            document_id=document_id,
            chunk_index=chunk_index,
            text=chunk,
            timestamp_start=None,
            timestamp_end=None,
            embedding_id=None,
        )

    print(f"Imported: {name} ({len(chunks)} chunks)")


def main():
    if len(sys.argv) >= 2 and os.path.isfile(sys.argv[1]):
        transcribe_local_file(sys.argv[1])
    else:
        limit = int(sys.argv[1]) if len(sys.argv) >= 2 else 10
        transcribe_plaud_recordings(limit=limit)


if __name__ == "__main__":
    main()
