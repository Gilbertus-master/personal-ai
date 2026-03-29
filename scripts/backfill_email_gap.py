#!/usr/bin/env python3
"""
Backfill email gap between PST import (up to 2026-03-15)
and MS Graph live sync (from 2026-03-24).

Queries MS Graph API for emails received between 2026-03-15 and 2026-03-24,
importing them through the standard pipeline with deduplication.
"""
from __future__ import annotations

import structlog
import logging
import time
from datetime import datetime

import requests

# Reuse the existing pipeline
from app.ingestion.graph_api.auth import get_access_token
from app.ingestion.graph_api.email_sync import (
    GRAPH_BASE,
    MS_GRAPH_USER_ID,
    _graph_get,
    _download_and_import_attachments,
    build_email_text,
    chunk_text,
    extract_participants,
)
from app.ingestion.common.db import (
    document_exists_by_raw_path,
    insert_chunk,
    insert_document,
    insert_source,
)

log = structlog.get_logger(__name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# The gap period
DATE_FROM = "2026-03-15T00:00:00Z"
DATE_TO = "2026-03-24T00:00:00Z"

SOURCE_TYPE = "email"

FOLDERS = [
    {"folder": "inbox", "source_name": "corporate_email"},
    {"folder": "sentitems", "source_name": "corporate_email_sent"},
]

# Graph API throttling / retry
MAX_RETRIES = 3
BACKOFF_SECS = 5


def backfill_folder(
    folder: str,
    source_name: str,
    token: str,
) -> tuple[int, int, int]:
    """
    Query Graph API for emails in folder within the gap period.
    Returns (imported, chunks_created, skipped).
    """
    source_id = insert_source(conn=None, source_type=SOURCE_TYPE, source_name=source_name)
    log.info(f"\n{'='*60}")
    log.info(f"Backfilling: {folder} (source_name={source_name}, source_id={source_id})")
    log.info(f"Period: {DATE_FROM} → {DATE_TO}")
    log.info(f"{'='*60}")

    user_path = f"users/{MS_GRAPH_USER_ID}" if MS_GRAPH_USER_ID else "me"
    base_url = f"{GRAPH_BASE}/{user_path}/mailFolders/{folder}/messages"

    params = {
        "$filter": f"receivedDateTime ge {DATE_FROM} and receivedDateTime lt {DATE_TO}",
        "$select": "subject,from,toRecipients,ccRecipients,bccRecipients,receivedDateTime,body,conversationId,hasAttachments",
        "$top": "50",
        "$orderby": "receivedDateTime asc",
    }

    imported = 0
    chunks_created = 0
    skipped = 0
    page = 0

    url = base_url

    while url:
        page += 1
        if page % 5 == 0:
            log.info(f"  Page {page}: imported={imported}, skipped={skipped}")

        # Fetch with retry
        data = None
        for attempt in range(MAX_RETRIES):
            try:
                if page == 1:
                    data = _graph_get(url, token, params)
                else:
                    # nextLink already includes params
                    data = _graph_get(url, token)
                break
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", 30))
                    log.info(f"  Throttled (429), waiting {retry_after}s...")
                    time.sleep(retry_after)
                elif e.response is not None and e.response.status_code >= 500:
                    wait = BACKOFF_SECS * (attempt + 1)
                    log.info(f"  Server error {e.response.status_code}, retry in {wait}s...")
                    time.sleep(wait)
                else:
                    raise
            except (requests.ConnectionError, requests.Timeout) as e:
                wait = BACKOFF_SECS * (attempt + 1)
                log.info(f"  Network error: {e}, retry in {wait}s...")
                time.sleep(wait)

        if data is None:
            log.info(f"  Failed to fetch page {page} after {MAX_RETRIES} retries, stopping.")
            break

        messages = data.get("value", [])
        if not messages and page == 1:
            log.info(f"  No messages found in {folder} for the gap period.")
            break

        for msg in messages:
            msg_id = msg.get("id", "")
            raw_path = f"graph://{source_name}/{folder}/{msg_id}"

            if document_exists_by_raw_path(raw_path):
                skipped += 1
                continue

            full_text = build_email_text(msg)
            chunks = chunk_text(full_text)
            participants = extract_participants(msg)

            received = None
            if msg.get("receivedDateTime"):
                try:
                    received = datetime.fromisoformat(
                        msg["receivedDateTime"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            sender_addr = msg.get("from", {}).get("emailAddress", {}).get("address")
            subject = msg.get("subject") or "(no subject)"

            document_id = insert_document(
                conn=None,
                source_id=source_id,
                title=subject,
                created_at=received,
                author=sender_addr,
                participants=participants,
                raw_path=raw_path,
            )

            for chunk_index, chunk in enumerate(chunks):
                insert_chunk(
                    conn=None,
                    document_id=document_id,
                    chunk_index=chunk_index,
                    text=chunk,
                    timestamp_start=received,
                    timestamp_end=received,
                    embedding_id=None,
                )

            imported += 1
            chunks_created += len(chunks)

            # Attachments
            if msg.get("hasAttachments"):
                try:
                    att_count = _download_and_import_attachments(
                        msg_id=msg_id, msg=msg, source_id=source_id, token=token,
                    )
                    if att_count:
                        log.info(f"    + {att_count} attachment(s): {subject[:50]}")
                except Exception as e:
                    log.warning("Attachment import failed for msg %s: %s", msg_id[:20], e)

            if imported % 10 == 0 and imported > 0:
                date_str = msg.get("receivedDateTime", "")[:10]
                log.info(f"  [{date_str}] {imported} imported so far... last: {subject[:60]}")

        # Pagination
        next_link = data.get("@odata.nextLink")
        url = next_link if next_link else None

    log.info(f"\n  Done: {imported} imported, {chunks_created} chunks, {skipped} skipped (dupes)")
    return imported, chunks_created, skipped


def main():
    log.info("Email Gap Backfill: 2026-03-15 → 2026-03-24")
    log.info("Source type: email")

    token = get_access_token()
    log.info("Auth OK.\n")

    total_imported = 0
    total_chunks = 0
    total_skipped = 0

    for folder_cfg in FOLDERS:
        imp, chk, skp = backfill_folder(
            folder=folder_cfg["folder"],
            source_name=folder_cfg["source_name"],
            token=token,
        )
        total_imported += imp
        total_chunks += chk
        total_skipped += skp

    log.info(f"\n{'='*60}")
    log.info("BACKFILL COMPLETE")
    log.info(f"  Total imported: {total_imported}")
    log.info(f"  Total chunks:   {total_chunks}")
    log.info(f"  Total skipped:  {total_skipped}")
    log.info(f"{'='*60}")


if __name__ == "__main__":
    main()
