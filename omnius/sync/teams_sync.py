"""Sync Microsoft Teams messages into Omnius documents/chunks.

Fetches messages from Teams channels the app has access to,
stores them as documents with classification based on channel type.
"""
from __future__ import annotations

import structlog
from datetime import datetime, timezone

from omnius.db.postgres import get_pg_connection
from omnius.sync.graph_api import graph_get_all

log = structlog.get_logger(__name__)


def sync_teams_messages(hours: int = 24) -> dict:
    """Sync Teams messages from the last N hours."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    stats = {"teams_found": 0, "channels_found": 0, "messages_synced": 0, "skipped": 0}

    try:
        # Get all teams the app has access to
        teams = graph_get_all("/teams", params={"$select": "id,displayName"})
        stats["teams_found"] = len(teams)

        for team in teams:
            team_id = team["id"]
            team_name = team.get("displayName", "Unknown")

            # Get channels
            channels = graph_get_all(f"/teams/{team_id}/channels",
                                      params={"$select": "id,displayName,membershipType"})
            stats["channels_found"] += len(channels)

            for channel in channels:
                channel_id = channel["id"]
                channel_name = channel.get("displayName", "Unknown")
                is_private = channel.get("membershipType") == "private"

                # Classify based on channel type
                classification = "confidential" if is_private else "internal"

                # Get recent messages
                try:
                    messages = graph_get_all(
                        f"/teams/{team_id}/channels/{channel_id}/messages",
                        params={
                            "$filter": f"lastModifiedDateTime gt {cutoff_iso}",
                            "$top": "50",
                            "$select": "id,body,from,createdDateTime,subject",
                        },
                        max_pages=5,
                    )
                except Exception as e:
                    log.warning("teams_channel_fetch_failed", team=team_name,
                                channel=channel_name, error=str(e))
                    continue

                for msg in messages:
                    msg_id = msg.get("id", "")
                    body = (msg.get("body", {}).get("content") or "").strip()
                    if not body or len(body) < 10:
                        stats["skipped"] += 1
                        continue

                    sender = (msg.get("from", {}).get("user", {}).get("displayName")
                              or "Unknown")
                    created = msg.get("createdDateTime", "")
                    subject = msg.get("subject") or f"Teams: {channel_name}"

                    # Upsert document + chunk
                    _upsert_teams_message(
                        source_id=f"teams:{team_id}:{channel_id}:{msg_id}",
                        title=f"[{team_name}/{channel_name}] {subject}",
                        content=f"[{sender}] {body}",
                        classification=classification,
                        created_at=created,
                    )
                    stats["messages_synced"] += 1

    except Exception as e:
        log.error("teams_sync_failed", error=str(e))
        stats["error"] = str(e)

    log.info("teams_sync_complete", **stats)
    return stats


def _upsert_teams_message(source_id: str, title: str, content: str,
                           classification: str, created_at: str):
    """Insert or skip Teams message (dedup by source_id)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Upsert document (handles edits)
            cur.execute("""
                INSERT INTO omnius_documents (source_type, source_id, title, content,
                                              classification, imported_at)
                VALUES ('teams', %s, %s, %s, %s, COALESCE(%s::timestamptz, NOW()))
                ON CONFLICT (source_id) DO UPDATE
                    SET content = EXCLUDED.content, title = EXCLUDED.title,
                        imported_at = EXCLUDED.imported_at
                RETURNING id
            """, (source_id, title, content, classification, created_at or None))
            doc_id = cur.fetchone()[0]

            # Upsert chunk (1:1 for messages)
            cur.execute("""
                INSERT INTO omnius_chunks (document_id, content, classification)
                VALUES (%s, %s, %s)
                ON CONFLICT (document_id) WHERE document_id = %s
                DO UPDATE SET content = EXCLUDED.content
            """, (doc_id, content, classification, doc_id))
        conn.commit()
