"""
Automatic Plaud sync — pulls transcriptions directly from Plaud API.

Uses auth token from Plaud Desktop local storage.
API endpoints reverse-engineered from arbuzmell/plaud-api.

Usage:
    python -m app.ingestion.plaud_sync          # sync latest 50
    python -m app.ingestion.plaud_sync 100      # sync latest 100
    python -m app.ingestion.plaud_sync --all     # sync all recordings
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import structlog
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.ingestion.common.db import (
    insert_chunks_batch,
    insert_document,
    insert_source,
)

load_dotenv()

log = structlog.get_logger(__name__)

PLAUD_API = "https://api.plaud.ai"
PLAUD_TOKEN_DIR = Path("/mnt/c/Users/jablo/AppData/Roaming/Plaud/Local Storage/leveldb")

CHUNK_TARGET_CHARS = 3000
CHUNK_OVERLAP_CHARS = 300


def get_plaud_token() -> str:
    """Extract auth token from Plaud Desktop local storage or env var."""
    token = os.getenv("PLAUD_AUTH_TOKEN")
    if token:
        return token

    for f in sorted(PLAUD_TOKEN_DIR.glob("*.log"), reverse=True):
        try:
            content = f.read_bytes().decode("utf-8", errors="ignore")
            match = re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", content)
            if match:
                return match.group(0)
        except Exception:
            continue

    raise RuntimeError("No Plaud token. Set PLAUD_AUTH_TOKEN or ensure Plaud Desktop is logged in.")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def list_recordings(token: str, limit: int = 50, skip: int = 0) -> list[dict[str, Any]]:
    """List recordings using /file/simple/web endpoint."""
    resp = requests.get(
        f"{PLAUD_API}/file/simple/web",
        headers=_headers(token),
        params={"skip": skip, "limit": limit, "is_trash": 0, "sort_by": "start_time", "is_desc": "true"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data_file_list", [])


def get_recording_details(token: str, file_ids: list[str]) -> list[dict[str, Any]]:
    """Get full details (including transcript) for recording IDs."""
    if not file_ids:
        return []
    resp = requests.post(
        f"{PLAUD_API}/file/list",
        headers={**_headers(token), "Content-Type": "application/json"},
        json=file_ids,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data_file_list", [])


def extract_transcript(recording: dict[str, Any]) -> str:
    """Extract transcript text from recording detail."""
    # Try trans_result (main transcript field)
    trans = recording.get("trans_result") or recording.get("transcript")
    if isinstance(trans, str) and trans.strip():
        return trans.strip()

    if isinstance(trans, dict):
        segments = trans.get("segments") or trans.get("utterances") or []
        if segments:
            parts = []
            for seg in segments:
                speaker = seg.get("speaker") or seg.get("speaker_name") or ""
                text = seg.get("text") or seg.get("content") or ""
                if speaker and text:
                    parts.append(f"{speaker}: {text}")
                elif text:
                    parts.append(text)
            return "\n".join(parts)

    if isinstance(trans, list):
        parts = []
        for seg in trans:
            if isinstance(seg, dict):
                speaker = seg.get("speaker") or ""
                text = seg.get("text") or seg.get("content") or ""
                if speaker and text:
                    parts.append(f"{speaker}: {text}")
                elif text:
                    parts.append(text)
            elif isinstance(seg, str):
                parts.append(seg)
        return "\n".join(parts)

    # Try AI content
    ai_content = recording.get("ai_content") or {}
    if isinstance(ai_content, dict):
        summary = ai_content.get("summary") or ai_content.get("text") or ""
        if summary:
            return summary

    return ""


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


def sync_plaud(limit: int = 50, sync_all: bool = False) -> tuple[int, int, int]:
    """Sync Plaud recordings into Gilbertus."""
    token = get_plaud_token()
    log.info("plaud_token_loaded", token_suffix=token[-20:])

    # Fetch recording list
    all_recordings: list[dict] = []
    skip = 0
    batch = min(limit, 50)

    while True:
        recs = list_recordings(token, limit=batch, skip=skip)
        if not recs:
            break
        all_recordings.extend(recs)
        if not sync_all and len(all_recordings) >= limit:
            all_recordings = all_recordings[:limit]
            break
        skip += len(recs)
        if len(recs) < batch:
            break

    log.info("plaud_recordings_found", count=len(all_recordings))

    if not all_recordings:
        return 0, 0, 0

    source_id = insert_source(source_type="audio_transcript", source_name="plaud_sync")

    # Check which are already imported — batch query all raw_paths and pending transcripts at once
    all_raw_paths = [f"plaud://sync/{rec.get('file_id') or rec.get('id') or ''}" for rec in all_recordings]
    all_file_ids = [rec.get("file_id") or rec.get("id") or "" for rec in all_recordings]
    all_file_ids = [fid for fid in all_file_ids if fid]

    existing_paths = set()
    pending_file_ids = set()

    if all_raw_paths:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT raw_path FROM documents WHERE raw_path = ANY(%s)",
                    (all_raw_paths,),
                )
                rows = cur.fetchall()
                existing_paths = {row[0] for row in rows}

    if all_file_ids:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT file_id FROM plaud_pending_transcripts WHERE file_id = ANY(%s)",
                    (all_file_ids,),
                )
                rows = cur.fetchall()
                pending_file_ids = {row[0] for row in rows}

    new_recordings = []
    skipped = 0
    skipped_pending = 0
    for rec in all_recordings:
        file_id = rec.get("file_id") or rec.get("id") or ""
        raw_path = f"plaud://sync/{file_id}"
        if raw_path in existing_paths:
            skipped += 1
        elif file_id in pending_file_ids:
            skipped_pending += 1
        else:
            new_recordings.append(rec)

    log.info("plaud_sync_status", new=len(new_recordings), skipped=skipped, skipped_pending=skipped_pending)

    if not new_recordings:
        return 0, 0, skipped + skipped_pending

    # Fetch full details with transcripts (batch of 10)
    imported = 0
    chunks_total = 0

    for i in range(0, len(new_recordings), 10):
        batch_recs = new_recordings[i:i + 10]
        file_ids = [r.get("file_id") or r.get("id") for r in batch_recs]
        file_ids = [fid for fid in file_ids if fid]

        if not file_ids:
            continue

        try:
            details = get_recording_details(token, file_ids)
        except Exception as e:
            log.error("plaud_details_error", error=str(e))
            continue

        for detail in details:
            file_id = detail.get("file_id") or detail.get("id") or ""
            title = detail.get("filename") or detail.get("title") or detail.get("name") or f"Plaud {file_id[:12]}"
            raw_path = f"plaud://sync/{file_id}"

            # Parse timestamp
            recorded_at = None
            start_time = detail.get("start_time")
            if start_time:
                try:
                    if isinstance(start_time, (int, float)):
                        ts = start_time / 1000 if start_time > 1e12 else start_time
                        recorded_at = datetime.fromtimestamp(ts)
                    else:
                        recorded_at = datetime.fromisoformat(str(start_time).replace("Z", "+00:00"))
                except (ValueError, TypeError, OSError):
                    pass

            transcript = extract_transcript(detail)
            is_pending = not transcript.strip()

            if is_pending:
                # Track pending transcripts to avoid re-fetching them repeatedly
                try:
                    with get_pg_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                "INSERT INTO plaud_pending_transcripts (file_id) VALUES (%s) ON CONFLICT (file_id) DO UPDATE SET last_checked_at = NOW()",
                                (file_id,),
                            )
                        conn.commit()
                except Exception as e:
                    log.warning("plaud_pending_tracking_failed", file_id=file_id, error=str(e))
                log.info("plaud_pending_transcript", title=title, file_id=file_id)
                continue

            # Build full text
            lines = [f"Transkrypcja: {title}"]
            if recorded_at:
                lines.append(f"Data: {recorded_at.strftime('%Y-%m-%d %H:%M')}")

            duration = detail.get("duration")
            if duration:
                mins = int(duration) // 60
                secs = int(duration) % 60
                lines.append(f"Czas trwania: {mins}m {secs}s")

            lines.append("")
            lines.append(transcript)
            full_text = "\n".join(lines)

            document_id = insert_document(
                source_id=source_id,
                title=title,
                created_at=recorded_at,
                author=None,
                participants=[],
                raw_path=raw_path,
            )

            chunks = chunk_text(full_text)
            chunks_payload = [
                {
                    "document_id": document_id,
                    "chunk_index": i,
                    "text": c,
                    "timestamp_start": recorded_at,
                    "timestamp_end": recorded_at,
                    "embedding_id": None,
                }
                for i, c in enumerate(chunks)
            ]
            insert_chunks_batch(chunks_payload)

            imported += 1
            chunks_total += len(chunks)
            log.info("plaud_recording_imported", title=title, chunks=len(chunks))

    log.info("plaud_sync_done", imported=imported, skipped=skipped, skipped_pending=skipped_pending, chunks=chunks_total)
    return imported, chunks_total, skipped + skipped_pending


def main() -> None:
    sync_all = "--all" in sys.argv
    limit = 50
    for arg in sys.argv[1:]:
        if arg != "--all":
            try:
                limit = int(arg)
            except ValueError:
                pass
    sync_plaud(limit=limit, sync_all=sync_all)


if __name__ == "__main__":
    main()
