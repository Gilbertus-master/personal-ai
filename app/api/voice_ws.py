"""
Voice WebSocket — real-time bidirectional voice dialog.

Architecture:
  Client → WebSocket → receive audio chunks → Whisper STT → Gilbertus → TTS → send audio back

Protocol:
  Client sends: binary audio chunks (PCM/WAV/MP3) terminated by text message "END"
  Server sends: text JSON {"type": "transcript", "text": "..."} then binary audio (TTS)

Conversation context is maintained per session (DB-backed).
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(tags=["voice_ws"])

WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:9090")
GILBERTUS_API = os.getenv("GILBERTUS_API_URL", "http://127.0.0.1:8000")
TTS_VOICE = os.getenv("TTS_VOICE", "pl-PL-ZofiaNeural")


# ================================================================
# Conversation memory (DB-backed)
# ================================================================

def _ensure_conversation_table():
    from app.db.postgres import get_pg_connection
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS voice_conversations (
                    id TEXT PRIMARY KEY,
                    messages JSONB NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            conn.commit()


def _get_conversation(conv_id: str) -> list[dict]:
    from app.db.postgres import get_pg_connection
    _ensure_conversation_table()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT messages FROM voice_conversations WHERE id = %s", (conv_id,))
            rows = cur.fetchall()
            if rows:
                return rows[0][0] if isinstance(rows[0][0], list) else json.loads(rows[0][0])
    return []


def _append_message(conv_id: str, role: str, text: str):
    from app.db.postgres import get_pg_connection
    _ensure_conversation_table()
    messages = _get_conversation(conv_id)
    messages.append({"role": role, "text": text, "timestamp": datetime.now(tz=timezone.utc).isoformat()})
    # Keep last 20 messages for context
    messages = messages[-20:]

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO voice_conversations (id, messages, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET messages = %s, updated_at = NOW()
            """, (conv_id, json.dumps(messages), json.dumps(messages)))
            conn.commit()


def _build_context(messages: list[dict]) -> str:
    """Build conversation context for Gilbertus."""
    if not messages:
        return ""
    lines = ["Poprzednia rozmowa głosowa:"]
    for m in messages[-10:]:
        prefix = "Sebastian" if m["role"] == "user" else "Gilbertus"
        lines.append(f"{prefix}: {m['text']}")
    return "\n".join(lines)


# ================================================================
# TTS helper
# ================================================================

async def _tts(text: str) -> bytes | None:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text[:1500], TTS_VOICE)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        data = buf.getvalue()
        return data if len(data) > 0 else None
    except ImportError:
        return None
    except Exception:
        return None


# ================================================================
# STT helper
# ================================================================

def _transcribe(audio_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp = f.name
    try:
        with open(tmp, "rb") as f:
            resp = requests.post(
                f"{WHISPER_URL}/transcribe",
                files={"file": ("audio.wav", f)},
                data={"language": "pl"},
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json().get("text", "").strip()
    except Exception as e:
        return f"[STT error: {e}]"
    finally:
        os.unlink(tmp)


# ================================================================
# WebSocket endpoint
# ================================================================

@router.websocket("/voice/ws")
async def voice_websocket(ws: WebSocket):
    """
    Real-time voice dialog.

    Protocol:
      1. Client sends text: {"action": "start", "conversation_id": "optional-uuid"}
      2. Client sends binary audio chunks
      3. Client sends text: "END" to signal end of utterance
      4. Server processes: STT → query → TTS
      5. Server sends text: {"type": "transcript", "text": "..."}
      6. Server sends text: {"type": "response", "text": "..."}
      7. Server sends binary: TTS audio (MP3)
      8. Server sends text: {"type": "done"}
      9. Loop to step 2
    """
    await ws.accept()

    conv_id = str(uuid.uuid4())

    try:
        # Wait for start message
        init = await ws.receive_text()
        init_data = json.loads(init)
        if init_data.get("conversation_id"):
            conv_id = init_data["conversation_id"]

        await ws.send_text(json.dumps({"type": "ready", "conversation_id": conv_id}))

        while True:
            # Collect audio chunks
            audio_buffer = io.BytesIO()
            while True:
                msg = await ws.receive()
                if msg.get("type") == "websocket.receive":
                    if msg.get("text") == "END":
                        break
                    if msg.get("text") == "CLOSE":
                        await ws.close()
                        return
                    if msg.get("bytes"):
                        audio_buffer.write(msg["bytes"])

            audio_data = audio_buffer.getvalue()
            if len(audio_data) < 100:
                await ws.send_text(json.dumps({"type": "error", "message": "Audio too short"}))
                continue

            # STT
            transcript = _transcribe(audio_data)
            await ws.send_text(json.dumps({"type": "transcript", "text": transcript}))

            if not transcript or transcript.startswith("[STT error"):
                await ws.send_text(json.dumps({"type": "done"}))
                continue

            # Save user message
            _append_message(conv_id, "user", transcript)

            # Check if it's a command
            from app.orchestrator.task_monitor import classify_message
            classification = classify_message(transcript)
            cmd_type = classification.get("type", "chat")

            if cmd_type == "query_command":
                from app.api.voice import _execute_query_command
                response_text = _execute_query_command(classification["command"])
            else:
                # Regular question with conversation context
                context = _build_context(_get_conversation(conv_id))
                try:
                    ask_resp = requests.post(
                        f"{GILBERTUS_API}/ask",
                        json={
                            "query": transcript,
                            "answer_length": "medium",
                            "channel": "voice",
                            "context": context,
                        },
                        timeout=120,
                    )
                    response_text = ask_resp.json().get("answer", "Nie mam odpowiedzi.")
                except Exception as e:
                    response_text = f"Błąd: {e}"

            # Save assistant message
            _append_message(conv_id, "assistant", response_text)

            # Send response text
            await ws.send_text(json.dumps({"type": "response", "text": response_text}))

            # TTS
            audio = await _tts(response_text)
            if audio:
                await ws.send_bytes(audio)

            await ws.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
