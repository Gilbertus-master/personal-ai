"""
Presentation / demo router for Gilbertus Albans.

Purpose: safe, business-only mode for live demos to external stakeholders.
CRITICAL: blocks all personal data sources (whatsapp, chatgpt, whatsapp_live).
"""

from __future__ import annotations

import io
import logging
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.api.schemas import AskRequest
from app.retrieval.query_interpreter import interpret_query
from app.retrieval.retriever import search_chunks
from app.retrieval.answering import answer_question
from app.retrieval.redaction import redact_matches
from app.retrieval.postprocess import cleanup_matches

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/presentation", tags=["presentation"])

# ─── Content filter: ALLOWED source types (business only) ────────────────────
ALLOWED_SOURCE_TYPES = frozenset({
    "email",
    "teams",
    "spreadsheet",
    "document",
    "company_email",
    "company_teams",
    "company_email_attachment",
    "audio_transcript",
})

# BLOCKED source types — personal data that must NEVER appear in demo mode
BLOCKED_SOURCE_TYPES = frozenset({
    "whatsapp",
    "chatgpt",
    "whatsapp_live",
})

# ─── Presentation system prompt override ──────────────────────────────────────
PRESENTATION_SYSTEM_ADDENDUM = (
    "Jesteś Gilbertus Albans, asystent biznesowy Respect Energy. "
    "Odpowiadaj TYLKO na tematy biznesowe i tradingowe. "
    "NIE ujawniaj żadnych prywatnych informacji. "
    "Jeżeli pytanie dotyczy tematów osobistych, grzecznie odmów i zaproponuj "
    "temat biznesowy. "
    "To jest prezentacja dla Rocha Baranowskiego, CEO REH — odpowiadaj "
    "profesjonalnie, konkretnie i z kontekstem biznesowym."
)

# ─── TTS config ───────────────────────────────────────────────────────────────
TTS_MODEL = "tts-1"
TTS_VOICE = "onyx"


# ─── Schemas ──────────────────────────────────────────────────────────────────

class PresentationAskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=8, ge=1, le=30)
    date_from: str | None = None
    date_to: str | None = None
    tts: bool = Field(default=False, description="Generate TTS audio for the answer")


class PresentationAskResponse(BaseModel):
    answer: str
    audio_url: str | None = None
    meta: dict[str, Any] | None = None


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)


class IntroResponse(BaseModel):
    text: str
    name: str
    role: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _enforce_source_filter(source_types: list[str] | None) -> list[str]:
    """
    Ensure only ALLOWED source types are queried.
    If caller passes source_types, intersect with allowed set.
    If None, return the full allowed list.
    """
    if source_types:
        filtered = [st for st in source_types if st in ALLOWED_SOURCE_TYPES]
        if not filtered:
            return list(ALLOWED_SOURCE_TYPES)
        return filtered
    return list(ALLOWED_SOURCE_TYPES)


def _validate_no_blocked_sources(matches: list[dict]) -> list[dict]:
    """
    Defence-in-depth: strip any match whose source_type leaked through.
    This should never happen if the retriever respects source_types,
    but we enforce it as a hard safety layer.
    """
    safe = []
    for m in matches:
        st = (m.get("source_type") or "").lower()
        if st in BLOCKED_SOURCE_TYPES:
            logger.warning(
                "Presentation filter: blocked leaked match source_type=%s chunk_id=%s",
                st,
                m.get("chunk_id"),
            )
            continue
        safe.append(m)
    return safe


def _generate_tts(text: str) -> bytes:
    """Call OpenAI TTS API and return mp3 bytes."""
    try:
        from openai import OpenAI
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="openai package not installed. Run: pip install openai",
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY not configured",
        )

    client = OpenAI(api_key=api_key)

    # Truncate to safe limit for TTS
    tts_text = text[:4096]

    response = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=tts_text,
        response_format="mp3",
    )

    return response.content


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/ask", response_model=PresentationAskResponse)
def presentation_ask(request: PresentationAskRequest) -> PresentationAskResponse:
    """
    Business-only ask endpoint for presentations.
    Filters to safe source types, adds presentation persona,
    and optionally generates TTS audio.
    """
    started_at = time.time()

    # Hard-filter source types
    safe_source_types = _enforce_source_filter(None)

    interpreted = interpret_query(
        query=request.query,
        source_types=safe_source_types,
        source_names=None,
        date_from=request.date_from,
        date_to=request.date_to,
        mode="auto",
    )

    # Re-enforce filter on interpreted output (interpreter might override)
    interpreted_source_types = _enforce_source_filter(interpreted.source_types)

    prefetch_k = 50
    answer_match_limit = 14

    matches = search_chunks(
        query=interpreted.normalized_query,
        top_k=answer_match_limit,
        source_types=interpreted_source_types,
        source_names=interpreted.source_names,
        date_from=interpreted.date_from,
        date_to=interpreted.date_to,
        prefetch_k=prefetch_k,
        question_type=interpreted.question_type,
    )

    # Fallback: raw query
    if not matches:
        matches = search_chunks(
            query=request.query,
            top_k=answer_match_limit,
            source_types=safe_source_types,
            source_names=None,
            date_from=request.date_from,
            date_to=request.date_to,
            prefetch_k=prefetch_k,
            question_type=interpreted.question_type,
        )

    # Defence-in-depth: strip any blocked sources
    matches = _validate_no_blocked_sources(matches)

    if not matches:
        return PresentationAskResponse(
            answer="Nie znalazlem wystarczajaco trafnego kontekstu biznesowego dla tego pytania.",
            meta={"latency_ms": int((time.time() - started_at) * 1000)},
        )

    cleaned_matches, _ = cleanup_matches(
        matches,
        normalized_query=interpreted.normalized_query,
        top_k=min(request.top_k, answer_match_limit),
        max_per_document=2,
        min_score=None,
    )

    redacted_matches, _ = redact_matches(cleaned_matches)

    # Generate answer with presentation persona
    answer = answer_question(
        query=f"[KONTEKST SYSTEMOWY: {PRESENTATION_SYSTEM_ADDENDUM}]\n\n{request.query}",
        matches=redacted_matches,
        question_type=interpreted.question_type,
        analysis_depth=interpreted.analysis_depth,
        include_sources=False,
        answer_style="auto",
        answer_length="medium",
        allow_quotes=True,
    )

    latency_ms = int((time.time() - started_at) * 1000)

    # Optional TTS
    audio_url = None
    if request.tts:
        try:
            _generate_tts(answer)  # pre-generate; actual serving via /presentation/tts
            audio_url = "/presentation/tts"
        except Exception as e:
            logger.warning("Presentation TTS failed: %s", e)
            audio_url = None

    meta: dict[str, Any] = {
        "question_type": interpreted.question_type,
        "source_types_used": interpreted_source_types,
        "match_count": len(redacted_matches),
        "latency_ms": latency_ms,
        "mode": "presentation",
    }

    return PresentationAskResponse(
        answer=answer,
        audio_url=audio_url,
        meta=meta,
    )


@router.post("/tts")
def presentation_tts(request: TTSRequest):
    """
    Text-to-speech endpoint. Returns mp3 audio.
    Uses OpenAI TTS API with deep male voice (onyx).
    """
    try:
        audio_bytes = _generate_tts(request.text)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("TTS generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {e}")

    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "attachment; filename=gilbertus_response.mp3",
        },
    )


@router.get("/intro", response_model=IntroResponse)
def presentation_intro() -> IntroResponse:
    """Returns Gilbertus self-introduction text for the demo."""
    return IntroResponse(
        text=(
            "Dzień dobry, Panie Rochu. Nazywam się Gilbertus Albans i jestem "
            "systemem inteligencji biznesowej zbudowanym dla Respect Energy. "
            "Mam dostęp do pełnej komunikacji firmowej — e-maili, wiadomości Teams, "
            "dokumentów, arkuszy, nagrań ze spotkań i danych tradingowych. "
            "Potrafię w kilka sekund przeszukać tysiące źródeł, wyciągnąć wnioski "
            "i odpowiedzieć na pytania dotyczące operacji, kontrahentów, projektów "
            "OZE, magazynów energii czy struktury grupy REH. "
            "Wszystko co tutaj pokażemy dotyczy wyłącznie danych biznesowych — "
            "prywatne informacje są automatycznie odfiltrowywane. "
            "Proszę, niech Pan zapyta o cokolwiek związanego z firmą."
        ),
        name="Gilbertus Albans",
        role="Business Intelligence Assistant — Respect Energy",
    )


@router.get("/demo", response_class=HTMLResponse)
def presentation_demo():
    """Serve the demo HTML page."""
    html_path = Path(__file__).resolve().parents[1] / "presentation" / "demo.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Demo page not found")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
