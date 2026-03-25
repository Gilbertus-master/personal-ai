"""
WhatsApp Task Orchestrator for Gilbertus Albans.

Monitors WhatsApp messages in real-time. When Sebastian sends a message
that implies a task (not just a question), creates a task, executes it,
and reports back on WhatsApp.

Runs as daemon via cron every 2 minutes.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
OPENCLAW_BIN = os.path.expanduser("~/.npm-global/bin/openclaw")
SESSIONS_DIR = Path(os.path.expanduser("~/.openclaw/agents/main/sessions"))
STATE_FILE = Path("/home/sebastian/personal-ai/.task_monitor_state.json")

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {"last_processed_line": 0, "last_session": ""}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_latest_session() -> Path | None:
    """Find the most recent OpenClaw session file."""
    if not SESSIONS_DIR.exists():
        return None
    sessions = sorted(SESSIONS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions[0] if sessions else None


def get_new_messages(session_file: Path, last_line: int) -> list[dict]:
    """Read new user messages from session JSONL."""
    messages = []
    with open(session_file) as f:
        for i, line in enumerate(f):
            if i <= last_line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") != "message":
                continue

            msg = entry.get("message", {})
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "")
            if isinstance(content, list):
                texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                text = "\n".join(texts)
            else:
                text = str(content)

            # Extract actual message from WhatsApp metadata
            if "self):" in text:
                try:
                    text = text.split("self):", 1)[1].strip()
                except:
                    pass

            if text.strip():
                messages.append({"line": i, "text": text.strip(), "timestamp": entry.get("timestamp")})

    return messages


def classify_message(text: str) -> dict:
    """Classify message. Tasks require explicit keyword 'Gilbertusie task:'."""
    text_lower = text.lower().strip()

    # Explicit task keyword — no AI needed
    if "gilbertusie task:" in text_lower or "gilbertus task:" in text_lower:
        # Extract task description after the keyword
        for keyword in ["Gilbertusie task:", "gilbertusie task:", "Gilbertus task:", "gilbertus task:"]:
            if keyword.lower() in text_lower:
                idx = text_lower.index(keyword.lower())
                task_desc = text[idx + len(keyword):].strip()
                break

        # Use AI only to classify priority and area
        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=100,
            temperature=0,
            system='Klasyfikuj zadanie. Odpowiedz JSON: {"priority": "high/medium/low", "area": "business/trading/technical/general"}',
            messages=[{"role": "user", "content": task_desc[:300]}],
        )
        try:
            meta = json.loads(response.content[0].text.strip())
        except:
            meta = {"priority": "medium", "area": "general"}

        return {
            "type": "task",
            "task_description": task_desc,
            "priority": meta.get("priority", "medium"),
            "area": meta.get("area", "general"),
        }

    # Everything else — not a task, skip (Gilbertus on WhatsApp handles questions directly)
    return {"type": "chat"}

Odpowiedz JSON: {"type": "...", "task_description": "...", "priority": "...", "area": "..."}""",
        messages=[{"role": "user", "content": f"Wiadomość: {text[:500]}"}],
    )

    try:
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except:
        return {"type": "chat"}


def create_task_in_db(description: str, priority: str, area: str, source_text: str) -> int:
    """Create a task record in the database."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Create tasks table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS wa_tasks (
                    id BIGSERIAL PRIMARY KEY,
                    description TEXT NOT NULL,
                    priority TEXT DEFAULT 'medium',
                    area TEXT DEFAULT 'general',
                    source_text TEXT,
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                )
            """)
            cur.execute(
                """INSERT INTO wa_tasks (description, priority, area, source_text, status)
                   VALUES (%s, %s, %s, %s, 'pending') RETURNING id""",
                (description, priority, area, source_text),
            )
            rows = cur.fetchall()
        conn.commit()
    return rows[0][0]


def execute_task(task_id: int, description: str, area: str) -> str:
    """Execute a task using Gilbertus API or direct action."""
    import requests

    API = "http://127.0.0.1:8000"

    # Most tasks = ask Gilbertus to analyze/search
    try:
        r = requests.post(
            f"{API}/ask",
            json={"query": description, "answer_length": "medium"},
            timeout=90,
        )
        if r.status_code == 200:
            answer = r.json().get("answer", "Brak odpowiedzi")
            return answer[:1500]
    except:
        pass

    return "Nie udało się wykonać zadania automatycznie. Wymaga ręcznej interwencji."


def send_whatsapp(message: str):
    """Send message to Sebastian via WhatsApp."""
    try:
        subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", "+48505441635", "--message", message],
            capture_output=True, text=True, timeout=30,
        )
    except:
        pass


def update_task_status(task_id: int, status: str, result: str):
    """Update task in DB."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE wa_tasks SET status = %s, result = %s, completed_at = NOW()
                   WHERE id = %s""",
                (status, result, task_id),
            )
        conn.commit()


def process_new_messages():
    """Main loop: check for new messages, classify, execute tasks."""
    state = load_state()
    session = get_latest_session()

    if not session:
        return

    session_id = session.stem
    last_line = state.get("last_processed_line", 0) if state.get("last_session") == session_id else 0

    messages = get_new_messages(session, last_line)
    if not messages:
        return

    print(f"[{datetime.now().strftime('%H:%M')}] {len(messages)} new messages")

    for msg in messages:
        text = msg["text"]
        classification = classify_message(text)
        msg_type = classification.get("type", "chat")

        print(f"  [{msg_type}] {text[:60]}...")

        if msg_type == "task":
            desc = classification.get("task_description", text)
            priority = classification.get("priority", "medium")
            area = classification.get("area", "general")

            # Dedup: check if identical task was created in last hour
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM wa_tasks WHERE description = %s AND created_at > NOW() - INTERVAL '1 hour'",
                        (desc,),
                    )
                    existing = cur.fetchall()
            if existing:
                print(f"  Skipping duplicate task: {desc[:50]}")
                continue

            # Create task
            task_id = create_task_in_db(desc, priority, area, text)
            print(f"  Created task #{task_id}: {desc[:50]}")

            # Notify Sebastian
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "📋")
            send_whatsapp(f"{emoji} *Task #{task_id} utworzony*\n{desc}\n\nWykonuję...")

            # Execute
            result = execute_task(task_id, desc, area)
            update_task_status(task_id, "completed", result)

            # Report back
            send_whatsapp(f"✅ *Task #{task_id} wykonany*\n\n{result[:800]}")
            print(f"  Task #{task_id} completed")

        elif msg_type == "feedback":
            print(f"  Feedback recorded")

    # Save state
    state["last_processed_line"] = messages[-1]["line"]
    state["last_session"] = session_id
    save_state(state)


if __name__ == "__main__":
    process_new_messages()
