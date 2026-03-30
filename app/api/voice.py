"""
Voice interface for Gilbertus — real-time dialog (not monologue).

Architecture:
  Browser/App → WebSocket → FastAPI → Whisper STT → Gilbertus /ask → TTS → audio back

Endpoints:
  POST /voice/ask — send audio file, get text answer + optional TTS audio
  POST /voice/transcribe — just transcribe audio to text
  POST /voice/command — voice command (same as WhatsApp: brief, market, competitors, status)
  POST /voice/tts — text to speech (returns audio file)
  GET  /voice/health — check pipeline status
"""
from __future__ import annotations

import io
import os
import tempfile

import requests
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/voice", tags=["voice"])

WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:9090")
TTS_VOICE = os.getenv("TTS_VOICE", "pl-PL-ZofiaNeural")  # Polish female voice


def _has_edge_tts() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


async def _synthesize_speech(text: str, voice: str = TTS_VOICE) -> bytes | None:
    """Generate speech audio from text using edge-tts. Returns MP3 bytes or None."""
    if not _has_edge_tts():
        return None
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        audio_bytes = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.write(chunk["data"])
        return audio_bytes.getvalue() if audio_bytes.tell() > 0 else None
    except Exception:
        return None


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), language: str = Form(default="pl")):
    """Transcribe audio file via Whisper."""
    content = await audio.read()

    # Save to temp file
    suffix = "." + (audio.filename.split(".")[-1] if audio.filename else "wav")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        # Send to Whisper
        with open(temp_path, "rb") as f:
            resp = requests.post(
                f"{WHISPER_URL}/transcribe",
                files={"file": (audio.filename or "audio.wav", f)},
                data={"language": language},
                timeout=120,
            )
        resp.raise_for_status()
        result = resp.json()
        return {"text": result.get("text", ""), "language": result.get("language", language)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.unlink(temp_path)


@router.post("/ask")
async def voice_ask(audio: UploadFile = File(...), language: str = Form(default="pl"), session_id: str = Form(default="anonymous")):
    """Transcribe audio → ask Gilbertus → return answer."""
    # Step 1: Transcribe
    content = await audio.read()
    suffix = "." + (audio.filename.split(".")[-1] if audio.filename else "wav")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        with open(temp_path, "rb") as f:
            resp = requests.post(
                f"{WHISPER_URL}/transcribe",
                files={"file": (audio.filename or "audio.wav", f)},
                data={"language": language},
                timeout=120,
            )
        resp.raise_for_status()
        transcript = resp.json().get("text", "")
    except Exception as e:
        return {"error": f"Transcription failed: {e}"}
    finally:
        os.unlink(temp_path)

    if not transcript or len(transcript.strip()) < 3:
        return {"error": "Empty transcript", "transcript": transcript}

    # Step 2: Ask Gilbertus
    try:
        ask_resp = requests.post(
            os.getenv("GILBERTUS_API_URL", "http://127.0.0.1:8000") + "/ask",
            json={"query": transcript, "answer_length": "medium", "channel": "voice", "session_id": session_id},
            timeout=120,
        )
        ask_data = ask_resp.json()
        answer = ask_data.get("answer", "Nie mam odpowiedzi.")
    except Exception as e:
        answer = f"Błąd przetwarzania: {e}"

    # Step 3: Optional TTS
    tts_available = False
    if _has_edge_tts():
        audio_data = await _synthesize_speech(answer[:1000])
        if audio_data:
            tts_available = True

    result = {
        "transcript": transcript,
        "answer": answer,
        "tts_available": tts_available,
        "meta": ask_data.get("meta") if "ask_data" in dir() else None,
    }

    return result


@router.post("/command")
async def voice_command(audio: UploadFile = File(...), language: str = Form(default="pl")):
    """Voice command: transcribe → classify → execute (same as WhatsApp commands)."""
    content = await audio.read()
    suffix = "." + (audio.filename.split(".")[-1] if audio.filename else "wav")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        with open(temp_path, "rb") as f:
            resp = requests.post(
                f"{WHISPER_URL}/transcribe",
                files={"file": (audio.filename or "audio.wav", f)},
                data={"language": language},
                timeout=120,
            )
        resp.raise_for_status()
        transcript = resp.json().get("text", "").strip()
    except Exception as e:
        return {"error": f"Transcription failed: {e}"}
    finally:
        os.unlink(temp_path)

    if not transcript or len(transcript) < 2:
        return {"error": "Empty transcript"}

    # Classify and execute command
    from app.orchestrator.task_monitor import classify_message
    classification = classify_message(transcript)
    cmd_type = classification.get("type", "chat")

    if cmd_type == "query_command":
        command = classification.get("command", "")
        response_text = _execute_query_command(command)
    elif cmd_type == "chat":
        # Regular question → ask Gilbertus
        try:
            ask_resp = requests.post(
                os.getenv("GILBERTUS_API_URL", "http://127.0.0.1:8000") + "/ask",
                json={"query": transcript, "answer_length": "medium", "channel": "voice"},
                timeout=120,
            )
            response_text = ask_resp.json().get("answer", "Nie mam odpowiedzi.")
        except Exception as e:
            response_text = f"Błąd: {e}"
    else:
        response_text = f"Komenda typu '{cmd_type}' rozpoznana. Treść: {transcript}"

    # Optional TTS
    audio_response = None
    if _has_edge_tts():
        audio_response = await _synthesize_speech(response_text[:1000])

    if audio_response:
        return StreamingResponse(
            io.BytesIO(audio_response),
            media_type="audio/mpeg",
            headers={"X-Transcript": transcript, "X-Response-Text": response_text[:200]},
        )

    return {"transcript": transcript, "command_type": cmd_type, "response": response_text}


def _execute_query_command(command: str) -> str:
    """Execute a query command and return text response."""
    try:
        if command == "brief":
            from app.retrieval.morning_brief import get_todays_brief
            brief = get_todays_brief()
            if brief and brief.get("text"):
                return brief["text"][:2000]
            return "Brak briefu na dziś. Wygeneruj komendą: brief"

        elif command == "market":
            from app.analysis.market_intelligence import get_market_dashboard
            d = get_market_dashboard(days=3)
            lines = ["Rynek energii, ostatnie 3 dni:"]
            for ins in d.get("insights", [])[:3]:
                lines.append(f"{ins['title']}. {ins.get('impact', '')}")
            return " ".join(lines) if len(lines) > 1 else "Brak nowych insightów rynkowych."

        elif command == "competitors":
            from app.analysis.competitor_intelligence import get_competitive_landscape
            landscape = get_competitive_landscape()
            lines = ["Przegląd konkurencji:"]
            for c in landscape.get("competitors", [])[:5]:
                if c.get("recent_signals_30d", 0) > 0:
                    lines.append(f"{c['name']}: {c['recent_signals_30d']} sygnałów.")
            return " ".join(lines) if len(lines) > 1 else "Brak nowych sygnałów o konkurencji."

        elif command == "status":
            from app.db.postgres import get_pg_connection
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM chunks")
                    chunks = cur.fetchall()[0][0]
                    cur.execute("SELECT COUNT(*) FROM events")
                    events = cur.fetchall()[0][0]
            return f"Gilbertus online. {chunks} chunków, {events} eventów w bazie. Wszystkie systemy sprawne."

        elif command == "scenarios":
            from app.analysis.scenario_analyzer import list_scenarios
            scenarios = list_scenarios(limit=3)
            if scenarios:
                lines = ["Ostatnie scenariusze:"]
                for s in scenarios:
                    lines.append(f"{s['title']}, wpływ: {s.get('total_impact_pln', 0):,.0f} złotych.")
                return " ".join(lines)
            return "Brak scenariuszy."

        elif command == "alerts":
            from app.analysis.market_intelligence import get_market_alerts
            alerts = get_market_alerts()
            if alerts:
                lines = ["Aktywne alerty:"]
                for a in alerts[:3]:
                    lines.append(f"{a['message'][:100]}.")
                return " ".join(lines)
            return "Brak aktywnych alertów."

        return f"Nieznana komenda: {command}"
    except Exception as e:
        return f"Błąd wykonania komendy: {e}"


@router.post("/tts")
async def text_to_speech(text: str = Form(...), voice: str = Form(default=TTS_VOICE)):
    """Convert text to speech. Returns MP3 audio."""
    if not _has_edge_tts():
        return {"error": "TTS not available. Install: pip install edge-tts"}

    audio = await _synthesize_speech(text, voice)
    if audio:
        return StreamingResponse(io.BytesIO(audio), media_type="audio/mpeg")
    return {"error": "TTS generation failed"}


@router.get("/health")
async def voice_health():
    """Check voice pipeline health."""
    whisper_ok = False
    try:
        resp = requests.get(f"{WHISPER_URL}/health", timeout=5)
        whisper_ok = resp.status_code == 200
    except Exception:
        pass

    return {
        "whisper": "ok" if whisper_ok else "down",
        "whisper_url": WHISPER_URL,
        "tts": "ok" if _has_edge_tts() else "not_installed (pip install edge-tts)",
        "tts_voice": TTS_VOICE,
        "mode": "http_request_response",
        "features": ["transcribe", "ask", "command", "tts"],
    }
