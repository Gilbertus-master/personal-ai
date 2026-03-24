"""
Incremental email sync via Microsoft Graph API delta queries.

Syncs Sebastian's corporate mailbox into Gilbertus.
Uses delta tokens for efficient incremental updates.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any
import re

import requests
from dotenv import load_dotenv

from app.ingestion.graph_api.auth import get_access_token
from app.ingestion.common.db import (
    document_exists_by_raw_path,
    insert_chunk,
    insert_document,
    insert_source,
)

load_dotenv()

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
MS_GRAPH_USER_ID = os.getenv("MS_GRAPH_USER_ID")  # email or object ID; if set, uses /users/{id}/ instead of /me/
DELTA_STATE_FILE = Path(__file__).resolve().parents[3] / ".ms_graph_email_delta.json"

CHUNK_TARGET_CHARS = 2500
CHUNK_OVERLAP_CHARS = 250


def _graph_get(url: str, token: str, params: dict | None = None) -> dict[str, Any]:
    """Make an authenticated GET request to Graph API."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _html_to_text(html: str) -> str:
    """Simple HTML to text conversion."""
    text = re.sub(r"(?is)<br\s*/?>", "\n", html)
    text = re.sub(r"(?is)</p>", "\n\n", html)
    text = re.sub(r"(?is)<.*?>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _save_delta_state(folder: str, delta_link: str) -> None:
    """Save delta link for incremental sync."""
    state = {}
    if DELTA_STATE_FILE.exists():
        try:
            state = json.loads(DELTA_STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    state[folder] = {"delta_link": delta_link, "updated_at": datetime.now().isoformat()}
    DELTA_STATE_FILE.write_text(json.dumps(state, indent=2))


def _load_delta_state(folder: str) -> str | None:
    """Load delta link for a folder."""
    if not DELTA_STATE_FILE.exists():
        return None
    try:
        state = json.loads(DELTA_STATE_FILE.read_text())
        return state.get(folder, {}).get("delta_link")
    except (json.JSONDecodeError, KeyError):
        return None


def chunk_text(text: str) -> list[str]:
    """Split email text into chunks."""
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


def build_email_text(msg: dict[str, Any]) -> str:
    """Build text representation of an email message."""
    lines = []

    subject = msg.get("subject") or "(no subject)"
    lines.append(f"Subject: {subject}")

    sender = msg.get("from", {}).get("emailAddress", {})
    if sender:
        lines.append(f"From: {sender.get('name', '')} <{sender.get('address', '')}>")

    to_list = msg.get("toRecipients", [])
    if to_list:
        to_str = ", ".join(
            f"{r.get('emailAddress', {}).get('name', '')} <{r.get('emailAddress', {}).get('address', '')}>"
            for r in to_list
        )
        lines.append(f"To: {to_str}")

    cc_list = msg.get("ccRecipients", [])
    if cc_list:
        cc_str = ", ".join(
            f"{r.get('emailAddress', {}).get('name', '')} <{r.get('emailAddress', {}).get('address', '')}>"
            for r in cc_list
        )
        lines.append(f"Cc: {cc_str}")

    received = msg.get("receivedDateTime")
    if received:
        lines.append(f"Date: {received}")

    lines.append("")

    body = msg.get("body", {})
    content = body.get("content", "")
    if body.get("contentType") == "html":
        content = _html_to_text(content)

    lines.append(content)

    return "\n".join(lines).strip()


def extract_participants(msg: dict[str, Any]) -> list[str]:
    """Extract all email participants."""
    participants = []

    sender = msg.get("from", {}).get("emailAddress", {}).get("address")
    if sender:
        participants.append(sender)

    for field in ["toRecipients", "ccRecipients", "bccRecipients"]:
        for r in msg.get(field, []):
            addr = r.get("emailAddress", {}).get("address")
            if addr:
                participants.append(addr)

    # Dedupe preserving order
    seen = set()
    deduped = []
    for p in participants:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def sync_folder(
    folder: str = "inbox",
    source_name: str = "corporate_email",
    limit: int | None = None,
) -> tuple[int, int, int]:
    """
    Sync emails from a Graph API folder using delta queries.
    Returns (imported, chunks_created, skipped).
    """
    token = get_access_token()
    source_type = "company_email"

    source_id = insert_source(conn=None, source_type=source_type, source_name=source_name)

    # Check for existing delta state
    delta_link = _load_delta_state(folder)

    if delta_link:
        print(f"Incremental sync (delta) for folder: {folder}")
        url = delta_link
    else:
        print(f"Initial full sync for folder: {folder}")
        user_path = f"users/{MS_GRAPH_USER_ID}" if MS_GRAPH_USER_ID else "me"
        url = f"{GRAPH_BASE}/{user_path}/mailFolders/{folder}/messages/delta"

    params = {
        "$select": "subject,from,toRecipients,ccRecipients,bccRecipients,receivedDateTime,body,conversationId",
        "$top": "50",
    }

    imported = 0
    chunks_created = 0
    skipped = 0
    page = 0

    while url:
        page += 1
        if page % 5 == 0:
            print(f"  Page {page}: imported={imported}, skipped={skipped}")

        if limit and imported >= limit:
            print(f"  Limit reached: {limit}")
            break

        try:
            if "delta" in url and "?" in url:
                data = _graph_get(url, token)
            else:
                data = _graph_get(url, token, params if page == 1 else None)
        except requests.HTTPError as e:
            print(f"  Graph API error: {e}")
            break

        messages = data.get("value", [])

        for msg in messages:
            # Skip removed messages (delta can return @removed)
            if "@removed" in msg:
                continue

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
                    received = datetime.fromisoformat(msg["receivedDateTime"].replace("Z", "+00:00"))
                except ValueError:
                    pass

            sender_addr = msg.get("from", {}).get("emailAddress", {}).get("address")

            document_id = insert_document(
                conn=None,
                source_id=source_id,
                title=msg.get("subject") or "(no subject)",
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

        # Handle pagination
        next_link = data.get("@odata.nextLink")
        delta_link_new = data.get("@odata.deltaLink")

        if delta_link_new:
            _save_delta_state(folder, delta_link_new)
            url = None  # Done
        elif next_link:
            url = next_link
        else:
            url = None

    print(f"Sync complete: {imported} imported, {chunks_created} chunks, {skipped} skipped")
    return imported, chunks_created, skipped


def main() -> None:
    """
    Usage:
        python -m app.ingestion.graph_api.email_sync
        python -m app.ingestion.graph_api.email_sync --folder inbox --limit 100
        python -m app.ingestion.graph_api.email_sync --folder sentitems
    """
    folder = "inbox"
    limit = None
    source_name = "corporate_email"

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--folder":
            folder = args[i + 1]
            i += 2
        elif args[i] == "--limit":
            limit = int(args[i + 1])
            i += 2
        elif args[i] == "--source-name":
            source_name = args[i + 1]
            i += 2
        else:
            i += 1

    sync_folder(folder=folder, source_name=source_name, limit=limit)


if __name__ == "__main__":
    main()
