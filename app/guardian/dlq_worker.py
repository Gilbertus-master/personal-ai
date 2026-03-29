"""
Dead Letter Queue retry worker.

Retries failed ingestion items from ingestion_dlq table.
Runs every 2 hours via cron. Abandoned items trigger WhatsApp alert (max 1x/day).

Usage:
    python -m app.guardian.dlq_worker
    python -m app.guardian.dlq_worker --dry-run
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

from app.db.postgres import get_pg_connection
from app.ingestion.common.db import document_exists_by_raw_path

log = structlog.get_logger(__name__)

WA_TARGET = os.getenv("WA_TARGET", "+48505441635")
ALERT_STATE_FILE = Path("/home/sebastian/personal-ai/.dlq_alert_state.json")


def get_pending_items(limit: int = 50) -> list[dict]:
    """Fetch pending/retrying DLQ items that haven't exceeded max_retries."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_type, source_name, raw_path, title,
                       error_message, error_type, payload, retry_count, max_retries
                FROM ingestion_dlq
                WHERE status IN ('pending', 'retrying')
                  AND retry_count < max_retries
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def mark_retrying(dlq_id: int) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_dlq
                SET status = 'retrying', last_retry_at = NOW()
                WHERE id = %s
                """,
                (dlq_id,),
            )
        conn.commit()


def mark_resolved(dlq_id: int) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_dlq
                SET status = 'resolved', resolved_at = NOW()
                WHERE id = %s
                """,
                (dlq_id,),
            )
        conn.commit()


def mark_failed(dlq_id: int, error_message: str) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_dlq
                SET retry_count = retry_count + 1,
                    last_retry_at = NOW(),
                    error_message = %s,
                    status = CASE
                        WHEN retry_count + 1 >= max_retries THEN 'abandoned'
                        ELSE 'pending'
                    END
                WHERE id = %s
                """,
                (error_message[:4000], dlq_id),
            )
        conn.commit()


def retry_item(item: dict) -> bool:
    """Attempt to re-import a DLQ item. Returns True on success."""
    source_type = item["source_type"]
    raw_path = item.get("raw_path")
    payload = item.get("payload") or {}

    # If already imported (e.g. manual retry succeeded), just resolve
    if raw_path and document_exists_by_raw_path(raw_path):
        return True

    if source_type == "email":
        return _retry_email(payload)
    elif source_type == "teams":
        return _retry_teams(payload)
    elif source_type == "document":
        return _retry_document(payload)
    elif source_type == "audio_transcript":
        return _retry_audio(payload)
    elif source_type == "whatsapp":
        return _retry_whatsapp(payload)
    elif source_type in ("whatsapp_live", "claude_code"):
        return _retry_live_ingest(source_type, payload)
    else:
        log.warning("dlq_unknown_source", source_type=source_type)
        return False


def _retry_email(payload: dict) -> bool:
    eml_path = payload.get("eml_path")
    if not eml_path or not Path(eml_path).exists():
        return False

    from app.ingestion.email.parser import parse_eml_file, build_email_text
    from app.ingestion.email.importer import chunk_text, build_participants
    from app.ingestion.common.db import insert_source, insert_document, insert_chunk

    pst_file = Path(payload.get("pst_file", ""))
    parsed = parse_eml_file(eml_path, pst_file, pst_file.parent)

    source_id = insert_source(conn=None, source_type="email", source_name=pst_file.name)
    document_id = insert_document(
        conn=None, source_id=source_id,
        title=parsed.subject or "(no subject)",
        created_at=parsed.sent_at,
        author=parsed.from_addr or "unknown",
        participants=build_participants(parsed),
        raw_path=parsed.raw_path,
    )
    full_text = build_email_text(parsed)
    for ci, chunk in enumerate(chunk_text(full_text)):
        insert_chunk(conn=None, document_id=document_id, chunk_index=ci,
                     text=chunk, timestamp_start=parsed.sent_at, timestamp_end=parsed.sent_at)
    return True


def _retry_teams(payload: dict) -> bool:
    file_path = payload.get("file_path")
    if not file_path or not Path(file_path).exists():
        return False

    from app.ingestion.teams.importer import import_one_thread
    return import_one_thread(file_path)


def _retry_document(payload: dict) -> bool:
    file_path = payload.get("file_path")
    if not file_path or not Path(file_path).exists():
        return False

    from app.ingestion.docs.importer import import_one_document
    return import_one_document(file_path)


def _retry_audio(payload: dict) -> bool:
    file_path = payload.get("file_path")
    if not file_path:
        return False

    # Plaud API sync items don't have local files
    if payload.get("stage") == "fetch_details" or payload.get("file_id"):
        # Re-trigger plaud sync for this item
        from app.ingestion.plaud_sync import sync_plaud
        sync_plaud(limit=10)
        return True

    if not Path(file_path).exists():
        return False

    from app.ingestion.audio.parser import parse_transcript_file
    from app.ingestion.audio.importer import import_transcript
    from app.ingestion.common.db import insert_source

    parsed = parse_transcript_file(Path(file_path))
    source_id = insert_source(conn=None, source_type="audio_transcript", source_name="plaud_pin_s")
    docs, _ = import_transcript(parsed, source_id)
    return docs > 0


def _retry_whatsapp(payload: dict) -> bool:
    file_path = payload.get("file_path")
    if not file_path or not Path(file_path).exists():
        return False

    # Re-run the whatsapp importer as subprocess (it's a main() script)
    result = subprocess.run(
        [sys.executable, "-m", "app.ingestion.whatsapp.importer", file_path],
        capture_output=True, text=True, timeout=120,
    )
    return result.returncode == 0


def _retry_live_ingest(source_type: str, payload: dict) -> bool:
    """For whatsapp_live and claude_code, re-trigger live ingest cycle."""
    from app.ingestion.live_ingest import run_all
    run_all()
    return True


def abandon_check() -> int:
    """Mark items that exceeded max_retries as abandoned. Returns count."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_dlq
                SET status = 'abandoned'
                WHERE status IN ('pending', 'retrying')
                  AND retry_count >= max_retries
                RETURNING id
                """
            )
            rows = cur.fetchall()
        conn.commit()
    return len(rows)


def send_abandoned_alert() -> None:
    """Send WhatsApp alert for abandoned DLQ items (max 1x/day)."""
    import json

    # Check last alert time
    last_alert = None
    if ALERT_STATE_FILE.exists():
        try:
            state = json.loads(ALERT_STATE_FILE.read_text())
            last_alert = state.get("last_dlq_alert")
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    if last_alert:
        try:
            last_dt = datetime.fromisoformat(last_alert)
            if (now - last_dt).total_seconds() < 86400:
                return  # Already alerted today
        except Exception:
            pass

    # Get abandoned items summary
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_type, COUNT(*), MIN(created_at)::text
                FROM ingestion_dlq
                WHERE status = 'abandoned'
                GROUP BY source_type
                ORDER BY COUNT(*) DESC
                """
            )
            rows = cur.fetchall()

    if not rows:
        return

    lines = ["\U0001f4e8 DLQ Abandoned Items Alert"]
    total = 0
    for source, count, oldest in rows:
        lines.append(f"  {source}: {count} items (oldest: {oldest[:16]})")
        total += count
    lines.append(f"Total: {total} abandoned items")
    lines.append("Review: GET /dlq?status=abandoned")

    msg = "\n".join(lines)
    log.warning("dlq_abandoned_alert", total=total)

    try:
        subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "whatsapp",
             "--target", WA_TARGET,
             "--message", msg],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        log.error("dlq_alert_send_failed", error=str(e))

    # Save alert timestamp
    ALERT_STATE_FILE.write_text(json.dumps({"last_dlq_alert": now.isoformat()}))


def run_worker(dry_run: bool = False) -> dict:
    """Main DLQ worker loop. Returns stats."""
    items = get_pending_items()
    stats = {"total": len(items), "resolved": 0, "failed": 0, "skipped": 0}

    if not items:
        log.info("dlq_worker_no_items")
        return stats

    log.info("dlq_worker_start", pending=len(items))

    for item in items:
        dlq_id = item["id"]

        if dry_run:
            log.info("dlq_dry_run", id=dlq_id, source=item["source_type"],
                     raw_path=item.get("raw_path", "")[:80])
            stats["skipped"] += 1
            continue

        mark_retrying(dlq_id)

        try:
            success = retry_item(item)
            if success:
                mark_resolved(dlq_id)
                stats["resolved"] += 1
                log.info("dlq_resolved", id=dlq_id, source=item["source_type"])
            else:
                mark_failed(dlq_id, "Retry returned False — item not importable")
                stats["failed"] += 1
                log.warning("dlq_retry_failed", id=dlq_id, source=item["source_type"])
        except Exception as e:
            mark_failed(dlq_id, str(e))
            stats["failed"] += 1
            log.warning("dlq_retry_error", id=dlq_id, error=str(e))

    # Check for newly abandoned items and alert
    abandoned = abandon_check()
    if abandoned > 0:
        stats["abandoned"] = abandoned
        send_abandoned_alert()

    log.info("dlq_worker_done", **stats)
    return stats


def main():
    dry_run = "--dry-run" in sys.argv
    stats = run_worker(dry_run=dry_run)
    print(f"DLQ Worker: {stats}")


if __name__ == "__main__":
    main()
