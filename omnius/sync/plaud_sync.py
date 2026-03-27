"""Per-user Plaud sync for Omnius.

Each CEO/board member can have their own Plaud Pin S device.
Recordings are classified as personal or corporate based on rules.
Personal = only owner sees. Corporate = visible in Omnius per RBAC.

Sync modes:
1. Webhook — real-time, Plaud pushes to /webhook/plaud/{user_id}
2. Pull API — cron every 15 min, fetches new recordings per user
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx
import structlog

from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

PLAUD_API_BASE = "https://api.plaud.ai"
CHUNK_TARGET = 3000
CHUNK_OVERLAP = 300


# ── Classification engine ──────────────────────────────────────────────────

def classify_recording(user_id: int, title: str, participants: list[str],
                       recorded_at: str | None = None) -> str:
    """Classify a recording as personal or corporate based on user rules.

    Rules checked in order:
    1. Participant rules — if any participant matches a personal rule → personal
    2. Keyword rules — if title matches a keyword rule → that classification
    3. Time range rules — if recorded during personal hours → personal
    4. Default rule — usually 'corporate'
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rule_type, pattern, classification
                FROM omnius_audio_rules
                WHERE user_id = %s
                ORDER BY
                    CASE rule_type
                        WHEN 'participant' THEN 1
                        WHEN 'keyword' THEN 2
                        WHEN 'time_range' THEN 3
                        WHEN 'default' THEN 4
                    END
            """, (user_id,))
            rules = cur.fetchall()

    for rule_type, pattern, classification in rules:
        if rule_type == "participant":
            if any(pattern.lower() in p.lower() for p in participants):
                return classification

        elif rule_type == "keyword":
            if pattern.lower() in (title or "").lower():
                return classification

        elif rule_type == "time_range" and recorded_at:
            try:
                from datetime import datetime
                rec_time = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
                parts = pattern.split("-")
                if len(parts) == 2:
                    start_h, start_m = map(int, parts[0].split(":"))
                    end_h, end_m = map(int, parts[1].split(":"))
                    rec_minutes = rec_time.hour * 60 + rec_time.minute
                    start_minutes = start_h * 60 + start_m
                    end_minutes = end_h * 60 + end_m
                    if start_minutes <= rec_minutes <= end_minutes:
                        return classification
            except (ValueError, IndexError):
                pass

        elif rule_type == "default":
            return classification

    return "corporate"


# ── Chunking ────────────────────────────────────────────────────────────────

def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + CHUNK_TARGET, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


# ── Webhook payload parsing ────────────────────────────────────────────────

def parse_plaud_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Extract transcript data from Plaud webhook/API payload."""
    transcript = data.get("transcript") or data.get("transcription") or {}
    segments = transcript.get("segments") or data.get("segments") or []

    recorded_at = None
    for field in ["recorded_at", "created_at", "timestamp"]:
        if data.get(field):
            try:
                from datetime import datetime
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
        "recorded_at_iso": recorded_at.isoformat() if recorded_at else None,
        "participants": sorted(participants),
        "full_text": "\n".join(text_lines).strip(),
        "duration": data.get("duration") or data.get("duration_seconds"),
    }


# ── Store recording ────────────────────────────────────────────────────────

def store_recording(user_id: int, parsed: dict[str, Any], source: str = "plaud_webhook") -> dict:
    """Store a Plaud recording as classified Omnius documents/chunks."""
    if not parsed["full_text"]:
        return {"status": "skipped", "reason": "empty transcription"}

    raw_path = f"plaud://{source}/{parsed['recording_id']}"

    # Dedup
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM omnius_documents WHERE source_id = %s", (raw_path,))
            if cur.fetchone():
                return {"status": "skipped", "reason": "already imported"}

    # Classify
    classification = classify_recording(
        user_id=user_id,
        title=parsed["title"],
        participants=parsed["participants"],
        recorded_at=parsed.get("recorded_at_iso"),
    )

    # Build text with metadata header
    lines = [f"Transkrypcja: {parsed['title']}"]
    if parsed["recorded_at"]:
        lines.append(f"Data: {parsed['recorded_at'].strftime('%Y-%m-%d %H:%M')}")
    if parsed["participants"]:
        lines.append(f"Uczestnicy: {', '.join(parsed['participants'])}")
    lines.append("")
    lines.append(parsed["full_text"])
    full_text = "\n".join(lines)

    # Store
    chunks = chunk_text(full_text)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO omnius_documents
                    (source_type, source_id, title, content, classification, owner_user_id,
                     metadata, imported_at)
                VALUES ('audio_transcript', %s, %s, %s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()))
                RETURNING id
            """, (
                raw_path,
                parsed["title"],
                full_text[:500],  # preview in content column
                classification,
                user_id,
                json.dumps({
                    "participants": parsed["participants"],
                    "duration": parsed["duration"],
                    "source": source,
                }),
                parsed["recorded_at"].isoformat() if parsed["recorded_at"] else None,
            ))
            doc_id = cur.fetchone()[0]

            for i, chunk in enumerate(chunks):
                cur.execute("""
                    INSERT INTO omnius_chunks (document_id, content, classification)
                    VALUES (%s, %s, %s)
                """, (doc_id, chunk, classification))
        conn.commit()

    log.info("plaud_recording_stored",
             user_id=user_id, doc_id=doc_id, title=parsed["title"][:80],
             classification=classification, chunks=len(chunks))

    return {
        "status": "imported",
        "document_id": doc_id,
        "chunks": len(chunks),
        "classification": classification,
        "title": parsed["title"],
    }


# ── Webhook verification ───────────────────────────────────────────────────

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Plaud webhook HMAC SHA256 signature."""
    if not secret:
        return True
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Pull sync (API-based) ──────────────────────────────────────────────────

def sync_user_plaud(user_id: int, limit: int = 50) -> dict:
    """Sync recordings for a specific user from Plaud API."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT plaud_auth_token FROM omnius_plaud_config
                WHERE user_id = %s AND auto_sync = TRUE
            """, (user_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                return {"status": "skipped", "reason": "no plaud token configured"}
            token = row[0]

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    stats = {"fetched": 0, "imported": 0, "skipped": 0}

    try:
        with httpx.Client(timeout=30.0) as client:
            # List recordings
            resp = client.get(
                f"{PLAUD_API_BASE}/file/simple/web",
                headers=headers,
                params={"skip": 0, "limit": limit},
            )
            resp.raise_for_status()
            recordings = resp.json().get("data", [])
            stats["fetched"] = len(recordings)

            # Filter to transcribed only
            transcribed_ids = [
                r["_id"] for r in recordings
                if r.get("is_trans") or r.get("ori_ready")
            ]

            if not transcribed_ids:
                return stats

            # Fetch details in batches of 10
            for i in range(0, len(transcribed_ids), 10):
                batch = transcribed_ids[i:i + 10]
                detail_resp = client.post(
                    f"{PLAUD_API_BASE}/file/list",
                    headers=headers,
                    json={"ids": batch},
                )
                detail_resp.raise_for_status()
                details = detail_resp.json().get("data", [])

                for rec in details:
                    # Extract transcript text
                    text = ""
                    if rec.get("trans_result"):
                        text = rec["trans_result"]
                    elif rec.get("transcript"):
                        text = rec["transcript"] if isinstance(rec["transcript"], str) else ""

                    if not text:
                        stats["skipped"] += 1
                        continue

                    parsed = parse_plaud_payload({
                        "id": rec.get("_id", ""),
                        "title": rec.get("name", "Plaud recording"),
                        "text": text,
                        "recorded_at": rec.get("created_at"),
                        "duration": rec.get("duration"),
                    })

                    result = store_recording(user_id, parsed, source="plaud_sync")
                    if result["status"] == "imported":
                        stats["imported"] += 1
                    else:
                        stats["skipped"] += 1

    except Exception as e:
        log.error("plaud_sync_failed", user_id=user_id, error=str(e))
        stats["error"] = str(e)

    log.info("plaud_sync_complete", user_id=user_id, **stats)
    return stats


def sync_all_users() -> dict:
    """Sync Plaud recordings for all users with auto_sync enabled."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pc.user_id, u.display_name
                FROM omnius_plaud_config pc
                JOIN omnius_users u ON u.id = pc.user_id
                WHERE pc.auto_sync = TRUE AND pc.plaud_auth_token IS NOT NULL
            """)
            users = cur.fetchall()

    results = {}
    for user_id, name in users:
        results[name] = sync_user_plaud(user_id)

    return results
