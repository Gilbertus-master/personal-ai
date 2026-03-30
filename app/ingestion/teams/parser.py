import json
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


@dataclass
class TeamsMessage:
    timestamp: datetime | None
    author: str
    text: str


@dataclass
class TeamsThread:
    thread_id: str
    conversation_id: str
    title: str
    created_at: datetime | None
    participants: list[str]
    messages: list[TeamsMessage]
    raw_path: str


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _clean_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _extract_itemdata(script_tag) -> dict[str, Any] | None:
    if not script_tag or not script_tag.string:
        return None

    raw = script_tag.string.strip()
    if not raw:
        return None

    try:
        outer = json.loads(raw)
        item_data_raw = outer.get("ItemData")
        if not item_data_raw:
            return None
        return json.loads(item_data_raw)
    except Exception:
        return None


def parse_teams_thread_html(file_path: str | Path) -> TeamsThread:
    path = Path(file_path)
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    message_divs = soup.select("div.message.message--chat")
    messages: list[TeamsMessage] = []
    participants: set[str] = set()
    thread_id = ""
    conversation_id = ""
    created_at = None
    title = path.stem

    for div in message_divs:
        author_el = div.select_one(".message__author")
        date_el = div.select_one(".message__date")
        time_el = div.select_one(".message__time")
        content_el = div.select_one(".message__content")

        author = _clean_text(author_el.get_text(" ", strip=True)) if author_el else "unknown"

        text = ""
        if content_el:
            # Prefer visible rendered text
            text = _clean_text(content_el.get_text("\n", strip=True))

        timestamp = None
        if date_el and time_el:
            dt_str = f"{date_el.get_text(strip=True)} {time_el.get_text(strip=True)}"
            # Example: 2/13/2023 7:06 AM
            for fmt in ("%m/%d/%Y %I:%M %p", "%d/%m/%Y %I:%M %p"):
                try:
                    timestamp = datetime.strptime(dt_str, fmt).replace(tzinfo=UTC)
                    break
                except ValueError:
                    pass

        scripts = div.find_all("script", attrs={"type": "application/json"})
        item_data = None
        for script in scripts:
            parsed = _extract_itemdata(script)
            if parsed and parsed.get("type") == "Message":
                item_data = parsed
                break

        if item_data:
            thread_id = thread_id or item_data.get("threadId", "")
            conversation_id = conversation_id or item_data.get("conversationId", "")
            created_at = created_at or _parse_iso_datetime(item_data.get("creationDate"))

            from_info = item_data.get("from") or {}
            from_name = from_info.get("displayName")
            if from_name:
                author = from_name

            to_list = item_data.get("to") or []
            if from_name:
                participants.add(from_name)
            for recipient in to_list:
                name = recipient.get("displayName")
                if name and not name.startswith("8:orgid:"):
                    participants.add(name)

            raw_content = item_data.get("content")
            if raw_content:
                # If embedded metadata has better content than visible text, keep it
                candidate = BeautifulSoup(raw_content, "html.parser").get_text("\n", strip=True)
                candidate = _clean_text(candidate)
                if candidate:
                    text = candidate

            if not timestamp:
                timestamp = _parse_iso_datetime(item_data.get("creationDate"))

        if author:
            participants.add(author)

        if not text and author:
            text = "[attachment or non-text message]"

        if text:
            messages.append(
                TeamsMessage(
                    timestamp=timestamp,
                    author=author,
                    text=text,
                )
            )

    messages.sort(key=lambda m: m.timestamp or datetime.min.replace(tzinfo=UTC))

    if messages and not created_at:
        created_at = messages[0].timestamp

    if not participants:
        participants = {m.author for m in messages if m.author}

    return TeamsThread(
        thread_id=thread_id or path.stem,
        conversation_id=conversation_id or path.stem,
        title=title,
        created_at=created_at,
        participants=sorted(p for p in participants if p),
        messages=messages,
        raw_path=str(path),
    )