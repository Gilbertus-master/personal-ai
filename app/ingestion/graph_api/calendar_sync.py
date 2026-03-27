"""
Calendar sync via Microsoft Graph API.

Fetches upcoming and recent calendar events from Sebastian's Outlook calendar.
Stores as source_type='calendar' with structured participant data.
Used by morning brief for meeting context.

Usage:
    python -m app.ingestion.graph_api.calendar_sync
    python -m app.ingestion.graph_api.calendar_sync --days-back 7 --days-ahead 3
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
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
MS_GRAPH_USER_ID = os.getenv("MS_GRAPH_USER_ID")


def _graph_get(url: str, token: str, params: dict | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_calendar_events(
    token: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Fetch calendar events in a date range."""
    user_path = f"users/{MS_GRAPH_USER_ID}" if MS_GRAPH_USER_ID else "me"
    url = f"{GRAPH_BASE}/{user_path}/calendarView"
    params = {
        "startDateTime": start.isoformat(),
        "endDateTime": end.isoformat(),
        "$top": "100",
        "$select": "id,subject,start,end,organizer,attendees,location,bodyPreview,isAllDay,isCancelled",
        "$orderby": "start/dateTime",
    }

    events = []
    while url:
        data = _graph_get(url, token, params if not events else None)
        events.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    return events


def format_event_text(event: dict[str, Any]) -> str:
    """Format a calendar event as readable text for chunking."""
    subject = event.get("subject", "(no subject)")
    start = event.get("start", {})
    end = event.get("end", {})
    start_str = start.get("dateTime", "?")[:16]
    end_str = end.get("dateTime", "?")[:16]

    organizer = event.get("organizer", {}).get("emailAddress", {})
    organizer_name = organizer.get("name", organizer.get("address", "?"))

    attendees = event.get("attendees", [])
    attendee_names = []
    for att in attendees:
        email = att.get("emailAddress", {})
        name = email.get("name", email.get("address", "?"))
        status = att.get("status", {}).get("response", "?")
        attendee_names.append(f"{name} ({status})")

    location = event.get("location", {}).get("displayName", "")
    body = event.get("bodyPreview", "")
    is_cancelled = event.get("isCancelled", False)

    lines = [
        f"Calendar Event: {subject}",
        f"Start: {start_str}",
        f"End: {end_str}",
        f"Organizer: {organizer_name}",
    ]
    if attendee_names:
        lines.append(f"Attendees: {', '.join(attendee_names)}")
    if location:
        lines.append(f"Location: {location}")
    if is_cancelled:
        lines.append("Status: CANCELLED")
    if body:
        lines.append(f"\n{body}")

    return "\n".join(lines)


def extract_participants(event: dict[str, Any]) -> list[str]:
    """Extract participant names from event."""
    names = []
    organizer = event.get("organizer", {}).get("emailAddress", {})
    if organizer.get("name"):
        names.append(organizer["name"])
    for att in event.get("attendees", []):
        email = att.get("emailAddress", {})
        if email.get("name"):
            names.append(email["name"])
    return names


def sync_calendar(
    days_back: int = 7,
    days_ahead: int = 3,
    source_name: str = "corporate_calendar",
) -> tuple[int, int]:
    """Sync calendar events."""
    token = get_access_token()

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days_back)
    end = now + timedelta(days=days_ahead)

    print(f"Fetching calendar: {start.date()} to {end.date()}")
    events = fetch_calendar_events(token, start, end)
    print(f"Found {len(events)} calendar events")

    source_id = insert_source(conn=None, source_type="calendar", source_name=source_name)

    imported = 0
    chunks_created = 0

    for event in events:
        event_id = event.get("id", "")
        raw_path = f"graph://calendar/{event_id}"

        if document_exists_by_raw_path(raw_path):
            continue

        subject = event.get("subject", "(no subject)")
        start_dt = None
        if event.get("start", {}).get("dateTime"):
            try:
                start_dt = datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
            except ValueError:
                pass

        participants = extract_participants(event)
        text = format_event_text(event)

        if len(text) < 20:
            continue

        document_id = insert_document(
            conn=None,
            source_id=source_id,
            title=f"Calendar: {subject}",
            created_at=start_dt,
            author=participants[0] if participants else None,
            participants=participants,
            raw_path=raw_path,
        )


        insert_chunk(
            conn=None,
            document_id=document_id,
            chunk_index=0,
            text=text,
            timestamp_start=start_dt,
            timestamp_end=start_dt,
            embedding_id=None,
        )

        imported += 1
        chunks_created += 1

    print(f"Calendar sync: {imported} events imported, {chunks_created} chunks")
    return imported, chunks_created


def get_today_events(token: str | None = None) -> list[dict[str, Any]]:
    """Fetch today's calendar events (for morning brief)."""
    if token is None:
        token = get_access_token()

    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    return fetch_calendar_events(token, start, end)


def main() -> None:
    days_back = 7
    days_ahead = 3

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--days-back":
            days_back = int(args[i + 1])
            i += 2
        elif args[i] == "--days-ahead":
            days_ahead = int(args[i + 1])
            i += 2
        else:
            i += 1

    sync_calendar(days_back=days_back, days_ahead=days_ahead)


if __name__ == "__main__":
    main()
