"""
Plaud monitoring and automation pipeline.

Pipeline: Plaud Pin S → (Bluetooth/app sync) → Plaud Cloud → auto-trigger
          transcription → poll for completion → import to Gilbertus →
          embed → extract entities/events.

The ONLY manual step is syncing Plaud Pin S with the phone app.
Everything else is fully automatic.

Usage:
    python -m app.ingestion.plaud_monitor
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone

import requests
import structlog

from app.ingestion.common.db import document_exists_by_raw_path
from app.ingestion.plaud_sync import get_plaud_token, list_recordings, sync_plaud

log = structlog.get_logger(__name__)


def run_monitor() -> None:
    """Run the full Plaud monitoring pipeline."""
    try:
        token = get_plaud_token()
    except RuntimeError as e:
        log.error("failed_to_get_token", error=str(e))
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

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

    now = datetime.now(tz=timezone.utc)

    needs_transcription = []
    transcribed = []

    for r in all_recs:
        trans = r.get("is_trans", False)
        if trans:
            transcribed.append(r)
        else:
            needs_transcription.append(r)

    # Cross-reference is_trans against DB to detect unreliable field values.
    # If is_trans=False but recording IS already in DB → field was wrong when it was processed.
    is_trans_false_but_in_db = [
        r for r in needs_transcription
        if document_exists_by_raw_path(f"plaud://sync/{r['id']}")
    ]
    if is_trans_false_but_in_db:
        log.warning(
            "is_trans_field_discrepancy",
            count=len(is_trans_false_but_in_db),
            ids=[r["id"] for r in is_trans_false_but_in_db],
            note="Recordings have is_trans=False but are already in DB — field may be unreliable (see Lessons Learned #16)",
        )

    log.info(
        "plaud_scan_complete",
        timestamp=now.strftime("%Y-%m-%d %H:%M"),
        total=len(all_recs),
        transcribed=len(transcribed),
        need_transcription=len(needs_transcription),
    )

    # --- Step 2: Auto-trigger transcription (2-step: PATCH config + POST trigger) ---
    triggered = 0
    for r in needs_transcription:
        fid = r["id"]
        name = r.get("filename", "?")
        dur = r.get("duration", 0) / 1000
        # Skip very short recordings (<10s) — likely accidental
        if dur < 10:
            continue
        try:
            # Step 2a: Configure transcription via PATCH
            patch_resp = requests.patch(
                f"https://api.plaud.ai/file/{fid}",
                headers=headers,
                json={
                    "extra_data": {"tranConfig": {"language": "auto", "trans_type": 1}}
                },
                timeout=15,
            )
            if patch_resp.status_code not in (200, 204):
                log.warning(
                    "transcription_config_failed",
                    filename=name,
                    status=patch_resp.status_code,
                )
                continue
            # Step 2b: Trigger transcription via POST
            resp = requests.post(
                f"https://api.plaud.ai/ai/transsumm/{fid}",
                headers={
                    **headers,
                    "Origin": "https://web.plaud.ai",
                    "Referer": "https://web.plaud.ai/",
                },
                json={
                    "language": "auto",
                    "summ_type": 1,
                    "support_mul_summ": True,
                    "info": json.dumps({"language": "auto", "summary_type": 1}),
                },
                timeout=30,
            )
            data = resp.json()
            if data.get("status") == 0 or "processing" in str(
                data.get("msg", "")
            ).lower():
                triggered += 1
                log.info(
                    "transcription_triggered",
                    filename=name,
                    duration_s=f"{dur:.0f}",
                )
            elif "already" in str(data.get("msg", "")).lower():
                pass  # Already processing, skip
            else:
                msg = data.get("msg", "?")
                err = data.get("err_msg", "")
                status_code = data.get("status")
                log.info(
                    "trigger_result",
                    filename=name,
                    status=status_code,
                    msg=msg,
                    err=err,
                )
        except Exception as e:
            log.error("error_triggering_transcription", filename=name, error=str(e))

    if triggered:
        log.info("transcription_batch_triggered", count=triggered)

    # --- Step 2c: Fallback to local Whisper for any still-untranscribed ---
    # Only run Whisper if no cloud transcriptions were triggered this cycle.
    # If triggered > 0, cloud is actively processing — wait for next cycle.
    if needs_transcription and not triggered:
        whisper_script = str(pathlib.Path(__file__).parent / "whisper_transcribe.py")
        log.info(
            "running_whisper_fallback",
            count=len(needs_transcription),
        )
        try:
            result = subprocess.run(
                [sys.executable, whisper_script, str(len(needs_transcription))],
                capture_output=True,
                text=True,
                timeout=3600,
            )
            if result.stdout:
                for line in result.stdout.strip().splitlines():
                    log.info("whisper_output", line=line)
            if result.returncode != 0 and result.stderr:
                log.error(
                    "whisper_error",
                    stderr=result.stderr[:200],
                )
        except Exception as e:
            log.error("whisper_execution_failed", error=str(e))

    # --- Step 3: Import all transcribed recordings (paginate) ---
    imported, chunks, skipped = 0, 0, 0
    try:
        imported, chunks, skipped = sync_plaud(limit=50, sync_all=True)
    except Exception as e:
        log.error("plaud_sync_failed", error=str(e))
    if imported:
        log.info("plaud_import_complete", imported=imported, chunks=chunks)

    # --- Step 4: Embed + extract on new data ---
    if imported:
        # Embed
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "app.retrieval.index_chunks",
                    "--batch-size",
                    "100",
                    "--limit",
                    "500",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "TIKTOKEN_CACHE_DIR": "/tmp/tiktoken_cache"},
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    if "indeksowano" in line.lower() or "indexed" in line.lower():
                        log.info("embedding_status", message=line)
            else:
                log.error("embedding_failed", returncode=result.returncode)
        except Exception as e:
            log.error("embed_step_error", error=str(e))

        # Extract entities
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "app.extraction.entities",
                    "--candidates-only",
                    str(min(chunks * 3, 100)),
                ],
                capture_output=True,
                timeout=180,
                env={
                    **os.environ,
                    "ANTHROPIC_EXTRACTION_MODEL": "claude-haiku-4-5",
                },
            )
            if result.returncode == 0:
                log.info("entity_extraction_complete", audio_data=True)
            else:
                log.error(
                    "entity_extraction_failed",
                    returncode=result.returncode,
                    stderr=result.stderr[:300] if result.stderr else "",
                )
        except Exception as e:
            log.error("entity_extraction_error", error=str(e))

    skipped_short = sum(1 for r in needs_transcription if r.get('duration', 0) / 1000 < 10)
    remaining = len(needs_transcription) - triggered - skipped_short
    if skipped_short:
        log.info(
            "transcription_skipped_short",
            count=skipped_short,
            note="recordings < 10s skipped by design",
        )
    if remaining > 0:
        log.info(
            "transcription_pending",
            count=remaining,
            note="recordings still awaiting transcription",
        )


def main() -> None:
    """Entry point for the monitor."""
    run_monitor()


if __name__ == "__main__":
    main()
