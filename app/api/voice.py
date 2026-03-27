"""
Voice interface for Gilbertus — real-time dialog (not monologue).

Architecture:
  Browser/App → WebSocket → FastAPI → Whisper STT → Gilbertus /ask → TTS → audio back

For now: HTTP endpoint that accepts audio, transcribes, processes, returns text+audio.
WebSocket streaming version requires dedicated server (Faza C on Hetzner).

Usage:
  POST /voice/ask — send audio file, get text answer + optional TTS audio
  POST /voice/transcribe — just transcribe audio to text
"""
from __future__ import annotations

import os
import tempfile

import requests
from fastapi import APIRouter, UploadFile, File, Form
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/voice", tags=["voice"])

WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:9090")


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
async def voice_ask(audio: UploadFile = File(...), language: str = Form(default="pl")):
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
            json={"query": transcript, "answer_length": "medium", "channel": "voice"},
            timeout=120,
        )
        ask_data = ask_resp.json()
        answer = ask_data.get("answer", "Nie mam odpowiedzi.")
    except Exception as e:
        answer = f"Błąd przetwarzania: {e}"

    return {
        "transcript": transcript,
        "answer": answer,
        "meta": ask_data.get("meta") if "ask_data" in dir() else None,
    }


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
        "mode": "http_request_response",
        "note": "WebSocket streaming available after Hetzner migration",
    }
