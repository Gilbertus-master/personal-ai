"""
Plaud webhook receiver — auto-imports transcriptions when Plaud finishes processing.

Plaud sends POST with transcription data when recording is transcribed.
This endpoint receives it, parses, chunks, and stores in Gilbertus.

Setup:
1. Register at https://www.plaud.ai/pages/developer-platform
2. Create webhook subscription for "transcription.completed" event
3. Set webhook URL to: https://<your-domain>/webhook/plaud
4. Set PLAUD_WEBHOOK_SECRET in .env
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from dotenv import load_dotenv

from app.ingestion.common.db import (
    document_exists_by_raw_path,
    insert_chunk,
    insert_document,
    insert_source,
)

load_dotenv()

PLAUD_WEBHOOK_SECRET = os.getenv("PLAUD_WEBHOOK_SECRET", "")

router = APIRouter(prefix="/webhook", tags=["webhook"])

CHUNK_TARGET_CHARS = 3000
CHUNK_OVERLAP_CHARS = 300


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Plaud webhook signature (HMAC SHA256)."""
    if not secret:
        return True  # Skip verification if no secret configured
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


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


def parse_plaud_webhook_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Extract transcript data from Plaud webhook payload."""
    # Handle various Plaud payload structures
    transcript = data.get("transcript") or data.get("transcription") or {}
    segments = transcript.get("segments") or data.get("segments") or []

    recorded_at = None
    for field in ["recorded_at", "created_at", "timestamp"]:
        if data.get(field):
            try:
                recorded_at = datetime.fromisoformat(str(data[field]).replace("Z", "+00:00"))
                break
            except (ValueError, TypeError):
                pass

    participants = set()
    text_lines = []

    if isinstance(segments, list):
        for seg in segments:
            speaker = seg.get("speaker") or seg.get("speaker_name")
            text = seg.get("text") or seg.get("content") or ""
            if speaker:
                participants.add(speaker)
                text_lines.append(f"{speaker}: {text}")
            elif text:
                text_lines.append(text)
    elif isinstance(transcript, str):
        text_lines.append(transcript)

    # Fallback: try plain text field
    if not text_lines:
        plain = data.get("text") or data.get("content") or ""
        if plain:
            text_lines.append(plain)

    title = data.get("title") or data.get("name") or f"Plaud {recorded_at or 'recording'}"
    recording_id = data.get("id") or data.get("recording_id") or data.get("file_id") or ""

    return {
        "title": title,
        "recording_id": str(recording_id),
        "recorded_at": recorded_at,
        "participants": sorted(participants),
        "full_text": "\n".join(text_lines).strip(),
        "duration": data.get("duration") or data.get("duration_seconds"),
        "context": data.get("type") or data.get("context"),
    }


@router.post("/plaud")
async def plaud_webhook(request: Request) -> dict[str, Any]:
    """Receive Plaud webhook and auto-import transcription."""
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Plaud-Signature", "")
    if PLAUD_WEBHOOK_SECRET and not verify_signature(body, signature, PLAUD_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    parsed = parse_plaud_webhook_payload(data)

    if not parsed["full_text"]:
        return {"status": "skipped", "reason": "empty transcription"}

    raw_path = f"plaud://webhook/{parsed['recording_id']}"

    if document_exists_by_raw_path(raw_path):
        return {"status": "skipped", "reason": "already imported"}

    # Build full text with metadata header
    lines = [f"Transkrypcja: {parsed['title']}"]
    if parsed["recorded_at"]:
        lines.append(f"Data: {parsed['recorded_at'].strftime('%Y-%m-%d %H:%M')}")
    if parsed["participants"]:
        lines.append(f"Uczestnicy: {', '.join(parsed['participants'])}")
    lines.append("")
    lines.append(parsed["full_text"])
    full_text = "\n".join(lines)

    # Import
    source_id = insert_source(conn=None, source_type="audio_transcript", source_name="plaud_webhook")

    document_id = insert_document(
        conn=None,
        source_id=source_id,
        title=parsed["title"],
        created_at=parsed["recorded_at"],
        author=parsed["participants"][0] if parsed["participants"] else None,
        participants=parsed["participants"],
        raw_path=raw_path,
    )

    chunks = chunk_text(full_text)
    for chunk_index, chunk in enumerate(chunks):
        insert_chunk(
            conn=None,
            document_id=document_id,
            chunk_index=chunk_index,
            text=chunk,
            timestamp_start=parsed["recorded_at"],
            timestamp_end=parsed["recorded_at"],
            embedding_id=None,
        )

    return {
        "status": "imported",
        "document_id": document_id,
        "chunks": len(chunks),
        "title": parsed["title"],
        "participants": parsed["participants"],
    }
