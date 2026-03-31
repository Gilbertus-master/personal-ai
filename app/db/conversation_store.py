"""
Sliding window conversation memory.

Przechowuje ostatnie MAX_MESSAGES wiadomości per kanał/sesja.
Automatycznie przycina gdy okno jest za duże (token safety).

Użycie:
    store = ConversationStore("whatsapp:+48505441635")
    store.add("user", "Pytanie Sebastiana")
    store.add("assistant", "Odpowiedź Gilbertusa")
    history = store.get_history()
    context_str = store.as_context_string()
"""
from __future__ import annotations

import json
from typing import Literal

import structlog

from app.config.timezone import now as tz_now

log = structlog.get_logger("conversation_store")

MAX_MESSAGES = 20       # max liczba wiadomości w oknie
MAX_CHARS = 8_000       # max łączna długość znaków (bezpieczny limit tokenów)
CONTEXT_MSGS = 10       # ile ostatnich wiadomości wkładać do promptu


class ConversationStore:
    """Per-channel sliding window conversation memory."""

    def __init__(self, channel_key: str):
        """
        channel_key: unikalny identyfikator sesji, np.:
            "whatsapp:+48505441635"
            "voice:uuid-1234"
            "teams:conv-id-abc"
            "api:anonymous"
        """
        self.channel_key = channel_key

    # ──────────────────────────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────────────────────────

    def get_messages(self) -> list[dict]:
        """Returns full message list from DB."""
        try:
            from app.db.postgres import get_pg_connection
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT messages FROM conversation_windows WHERE channel_key = %s",
                        (self.channel_key,),
                    )
                    rows = cur.fetchall()
            if rows:
                msgs = rows[0][0] if isinstance(rows[0][0], list) else json.loads(rows[0][0])
                return msgs
        except Exception as e:
            log.warning("get_messages_failed", channel=self.channel_key, error=str(e))
        return []

    def get_history(self, n: int = CONTEXT_MSGS) -> list[dict]:
        """
        Returns last N messages formatted for Anthropic messages array.
        Format: [{"role": "user"|"assistant", "content": "..."}]
        """
        messages = self.get_messages()
        recent = messages[-n:] if len(messages) > n else messages
        return [{"role": m["role"], "content": m["text"]} for m in recent]

    def as_context_string(self, n: int = CONTEXT_MSGS) -> str:
        """
        Returns conversation history as readable string for prompt injection.
        Returns empty string if no history.
        """
        messages = self.get_messages()
        recent = messages[-n:] if len(messages) > n else messages
        if not recent:
            return ""

        lines = ["=== Poprzednie wiadomości w tej sesji ==="]
        for m in recent:
            role_label = "Sebastian" if m["role"] == "user" else "Gilbertus"
            text = m["text"][:500]
            if len(m["text"]) > 500:
                text += "...[obcięto]"
            lines.append(f"{role_label}: {text}")
        lines.append("=== Koniec historii ===\n")
        return "\n".join(lines)

    def get_last_answer_summary(self, max_chars: int = 500) -> str:
        """
        Returns truncated text of the last assistant message.
        Used for conversation-aware follow-up queries (gap targeting).
        """
        messages = self.get_messages()
        for m in reversed(messages):
            if m["role"] == "assistant":
                text = m["text"][:max_chars]
                if len(m["text"]) > max_chars:
                    text += "...[obcięto]"
                return text
        return ""

    # ──────────────────────────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────────────────────────

    def add(self, role: Literal["user", "assistant"], text: str) -> None:
        """Add message to window. Applies sliding window automatically."""
        if not text or not text.strip():
            return

        try:
            from app.db.postgres import get_pg_connection
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT messages FROM conversation_windows WHERE channel_key = %s FOR UPDATE",
                        (self.channel_key,),
                    )
                    rows = cur.fetchall()
                    if rows:
                        messages = rows[0][0] if isinstance(rows[0][0], list) else json.loads(rows[0][0])
                    else:
                        messages = []

                    messages.append({
                        "role": role,
                        "text": text.strip(),
                        "ts": tz_now().isoformat(),
                    })

                    messages = self._apply_window(messages)
                    total_chars = sum(len(m["text"]) for m in messages)

                    cur.execute(
                        """
                        INSERT INTO conversation_windows
                            (channel_key, messages, message_count, total_chars, last_active)
                        VALUES (%s, %s::jsonb, %s, %s, NOW())
                        ON CONFLICT (channel_key) DO UPDATE SET
                            messages      = EXCLUDED.messages,
                            message_count = EXCLUDED.message_count,
                            total_chars   = EXCLUDED.total_chars,
                            last_active   = NOW()
                        """,
                        (self.channel_key, json.dumps(messages, ensure_ascii=False),
                         len(messages), total_chars),
                    )
                conn.commit()

        except Exception as e:
            log.warning("add_message_failed", channel=self.channel_key, error=str(e))

    def clear(self) -> None:
        """Clear conversation window."""
        try:
            from app.db.postgres import get_pg_connection
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM conversation_windows WHERE channel_key = %s",
                        (self.channel_key,),
                    )
                conn.commit()
        except Exception as e:
            log.warning("clear_failed", channel=self.channel_key, error=str(e))

    # ──────────────────────────────────────────────────────────────
    # Window management
    # ──────────────────────────────────────────────────────────────

    def _apply_window(self, messages: list[dict]) -> list[dict]:
        """
        Apply sliding window constraints:
        1. Max MAX_MESSAGES messages
        2. Max MAX_CHARS total characters
        Always keeps most recent messages.
        """
        if len(messages) > MAX_MESSAGES:
            messages = messages[-MAX_MESSAGES:]

        while messages:
            total = sum(len(m["text"]) for m in messages)
            if total <= MAX_CHARS:
                break
            messages = messages[1:]

        return messages


# ──────────────────────────────────────────────────────────────────
# Convenience functions
# ──────────────────────────────────────────────────────────────────

def get_store(channel: str | None, session_id: str | None = None) -> ConversationStore:
    """
    Factory function — buduje channel_key z dostępnych parametrów.

    Przykłady:
      get_store("whatsapp", "+48505441635")  → "whatsapp:+48505441635"
      get_store("voice", "uuid-1234")         → "voice:uuid-1234"
      get_store("teams", "conv-abc")          → "teams:conv-abc"
      get_store(None)                         → "api:anonymous"
    """
    if channel and session_id:
        key = f"{channel}:{session_id}"
    elif channel:
        key = f"{channel}:default"
    else:
        key = "api:anonymous"
    return ConversationStore(key)


def cleanup_inactive_windows(hours: int = 24) -> int:
    """Delete conversation windows inactive for more than `hours`. Returns deleted count."""
    try:
        from app.db.postgres import get_pg_connection
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM conversation_windows "
                    "WHERE last_active < NOW() - INTERVAL %s",
                    (f"{hours} hours",),
                )
                deleted = cur.rowcount
            conn.commit()
        return deleted
    except Exception as e:
        log.warning("cleanup_inactive_windows_failed", hours=hours, error=str(e))
        return 0
