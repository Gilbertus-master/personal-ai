import json
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


@dataclass
class ChatGPTMessage:
    timestamp: datetime | None
    author: str
    text: str


@dataclass
class ChatGPTConversation:
    conversation_id: str
    title: str
    created_at: datetime | None
    messages: list[ChatGPTMessage]


def _ts(value) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def _extract_text_parts(message: dict[str, Any]) -> str:
    content = message.get("content") or {}
    parts = content.get("parts") or []

    text_parts = []
    for part in parts:
        if isinstance(part, str) and part.strip():
            text_parts.append(part.strip())

    return "\n".join(text_parts).strip()


def _flatten_messages(mapping: dict[str, Any]) -> list[ChatGPTMessage]:
    items = []

    for node in mapping.values():
        message = node.get("message")
        if not message:
            continue

        author = ((message.get("author") or {}).get("role")) or "unknown"
        text = _extract_text_parts(message)

        if not text:
            continue

        if author == "system":
            continue

        items.append(
            ChatGPTMessage(
                timestamp=_ts(message.get("create_time")),
                author=author,
                text=text,
            )
        )

    items.sort(key=lambda m: m.timestamp or datetime.min.replace(tzinfo=UTC))
    return items


def parse_chatgpt_export_file(file_path: str | Path) -> list[ChatGPTConversation]:
    path = Path(file_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    conversations: list[ChatGPTConversation] = []

    for item in data:
        mapping = item.get("mapping") or {}
        messages = _flatten_messages(mapping)

        if not messages:
            continue

        title = item.get("title") or item.get("conversation_id") or item.get("id") or path.stem
        created_at = _ts(item.get("create_time"))
        conversation_id = item.get("conversation_id") or item.get("id") or title

        conversations.append(
            ChatGPTConversation(
                conversation_id=conversation_id,
                title=title,
                created_at=created_at,
                messages=messages,
            )
        )

    return conversations