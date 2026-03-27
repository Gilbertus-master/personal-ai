"""
Incremental Teams chat sync via Microsoft Graph API.

Syncs Sebastian's personal Teams chats (1:1 and group) into Gilbertus.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
DELTA_STATE_FILE = Path(__file__).resolve().parents[3] / ".ms_graph_teams_delta.json"

CHUNK_TARGET_CHARS = 3000
CHUNK_OVERLAP_CHARS = 300


def _graph_get(url: str, token: str, params: dict | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _save_delta_state(chat_id: str, delta_link: str) -> None:
    state = {}
    if DELTA_STATE_FILE.exists():
        try:
            state = json.loads(DELTA_STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    state[chat_id] = {"delta_link": delta_link, "updated_at": datetime.now(tz=timezone.utc).isoformat()}
    DELTA_STATE_FILE.write_text(json.dumps(state, indent=2))


def _load_delta_state(chat_id: str) -> str | None:
    if not DELTA_STATE_FILE.exists():
        return None
    try:
        state = json.loads(DELTA_STATE_FILE.read_text())
        return state.get(chat_id, {}).get("delta_link")
    except (json.JSONDecodeError, KeyError):
        return None


def list_chats(token: str) -> list[dict[str, Any]]:
    """List all Teams chats the user is part of."""
    user_path = f"users/{MS_GRAPH_USER_ID}" if MS_GRAPH_USER_ID else "me"
    url = f"{GRAPH_BASE}/{user_path}/chats"
    params = {"$top": "50", "$select": "id,topic,chatType,lastUpdatedDateTime"}

    chats = []
    while url:
        data = _graph_get(url, token, params if not chats else None)
        chats.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    return chats


def sync_chat_messages(
    chat_id: str,
    chat_topic: str,
    source_id: int,
    token: str,
    limit: int | None = None,
) -> tuple[int, int]:
    """Sync messages from a single Teams chat."""
    delta_link = _load_delta_state(chat_id)

    if delta_link:
        url = delta_link
    else:
        user_path = f"users/{MS_GRAPH_USER_ID}" if MS_GRAPH_USER_ID else "me"
        url = f"{GRAPH_BASE}/{user_path}/chats/{chat_id}/messages"

    params = {"$top": "50"}
    imported = 0
    chunks_created = 0

    while url:
        if limit and imported >= limit:
            break

        try:
            data = _graph_get(url, token, params if not delta_link else None)
        except requests.HTTPError as e:
            print(f"  Error syncing chat {chat_topic}: {e}")
            break

        messages = data.get("value", [])

        # Group messages into conversation blocks (by time proximity)
        for msg in messages:
            if "@removed" in msg:
                continue

            msg_id = msg.get("id", "")
            raw_path = f"graph://teams/{chat_id}/{msg_id}"

            if document_exists_by_raw_path(raw_path):
                continue

            body = msg.get("body", {})
            content = body.get("content", "")
            if body.get("contentType") == "html":
                import re
                from html import unescape
                content = re.sub(r"(?is)<.*?>", " ", content)
                content = unescape(content).strip()

            if not content or len(content) < 10:
                continue

            sender = msg.get("from", {})
            sender_name = sender.get("user", {}).get("displayName") if sender else None
            created = None
            if msg.get("createdDateTime"):
                try:
                    created = datetime.fromisoformat(msg["createdDateTime"].replace("Z", "+00:00"))
                except ValueError:
                    pass

            title = f"Teams: {chat_topic or chat_id[:12]}"
            text = f"{sender_name or 'Unknown'}: {content}"

            document_id = insert_document(
                conn=None,
                source_id=source_id,
                title=title,
                created_at=created,
                author=sender_name,
                participants=[sender_name] if sender_name else [],
                raw_path=raw_path,
            )

            # Single message = single chunk (Teams messages are usually short)
            insert_chunk(
                conn=None,
                document_id=document_id,
                chunk_index=0,
                text=text,
                timestamp_start=created,
                timestamp_end=created,
                embedding_id=None,
            )

            imported += 1
            chunks_created += 1

        next_link = data.get("@odata.nextLink")
        delta_link_new = data.get("@odata.deltaLink")

        if delta_link_new:
            _save_delta_state(chat_id, delta_link_new)
            url = None
        elif next_link:
            url = next_link
        else:
            url = None

    return imported, chunks_created


def sync_all_chats(
    source_name: str = "corporate_teams",
    limit_per_chat: int | None = None,
) -> tuple[int, int]:
    """Sync all Teams chats."""
    token = get_access_token()
    source_type = "teams"

    source_id = insert_source(conn=None, source_type=source_type, source_name=source_name)

    chats = list_chats(token)
    print(f"Found {len(chats)} Teams chats")

    total_imported = 0
    total_chunks = 0

    for chat in chats:
        chat_id = chat["id"]
        topic = chat.get("topic") or chat.get("chatType", "unknown")
        print(f"  Syncing: {topic} ({chat.get('chatType')})")

        imported, chunks = sync_chat_messages(
            chat_id=chat_id,
            chat_topic=topic,
            source_id=source_id,
            token=token,
            limit=limit_per_chat,
        )

        total_imported += imported
        total_chunks += chunks

        if imported > 0:
            print(f"    → {imported} messages, {chunks} chunks")

    print(f"Teams sync complete: {total_imported} messages, {total_chunks} chunks")
    return total_imported, total_chunks


def main() -> None:
    """
    Usage:
        python -m app.ingestion.graph_api.teams_sync
        python -m app.ingestion.graph_api.teams_sync --limit 50
    """
    limit = None
    source_name = "corporate_teams"

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--limit":
            limit = int(args[i + 1])
            i += 2
        elif args[i] == "--source-name":
            source_name = args[i + 1]
            i += 2
        else:
            i += 1

    sync_all_chats(source_name=source_name, limit_per_chat=limit)


if __name__ == "__main__":
    main()
