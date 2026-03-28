"""
Microsoft Teams Bot integration for Gilbertus Albans.

Receives Bot Framework messages via webhook, processes them through the
BUSINESS-ONLY content filter (same as presentation mode), and responds
via Bot Framework REST API.

CRITICAL: uses the same source filter as /presentation/ask — no personal
data (whatsapp, chatgpt, whatsapp_live) is ever exposed.
"""

from __future__ import annotations

import asyncio
import structlog
import os
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from jwt import PyJWKClient, decode as jwt_decode
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, Field

from app.api.presentation import (
    _enforce_source_filter,
    _validate_no_blocked_sources,
)
from app.retrieval.query_interpreter import interpret_query
from app.retrieval.retriever import search_chunks
from app.retrieval.answering import answer_question
from app.retrieval.redaction import redact_matches
from app.retrieval.postprocess import cleanup_matches

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

log = structlog.get_logger("teams_bot")

router = APIRouter(prefix="/teams", tags=["teams"])

# ─── Azure Bot Framework config ──────────────────────────────────────────────
TEAMS_APP_ID = os.getenv("TEAMS_APP_ID", "")
TEAMS_APP_SECRET = os.getenv("TEAMS_APP_SECRET", "")
TEAMS_TENANT_ID = os.getenv("TEAMS_TENANT_ID", "")

BOT_FRAMEWORK_AUTH_URL = (
    f"https://login.microsoftonline.com/{TEAMS_TENANT_ID}/oauth2/v2.0/token"
    if TEAMS_TENANT_ID
    else "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
)
BOT_FRAMEWORK_SCOPE = "https://api.botframework.com/.default"

# ─── System prompt (business-only, same as presentation) ─────────────────────
TEAMS_SYSTEM_ADDENDUM = (
    "Jestes Gilbertus Albans, asystent biznesowy Respect Energy. "
    "Odpowiadaj TYLKO na tematy biznesowe i tradingowe. "
    "NIE ujawniaj zadnych prywatnych informacji. "
    "Jezeli pytanie dotyczy tematow osobistych, grzecznie odmow i zaproponuj "
    "temat biznesowy. "
    "Odpowiadaj profesjonalnie, konkretnie i z kontekstem biznesowym. "
    "Formatuj odpowiedzi w sposob czytelny w Microsoft Teams (uzywaj Markdown)."
)

# ─── Bot Framework JWT validation ────────────────────────────────────────────
_BOT_FRAMEWORK_OPENID_URL = (
    "https://login.botframework.com/v1/.well-known/openidconfiguration"
)
ALLOWED_SERVICE_URL_PREFIXES = (
    "https://smba.trafficmanager.net",
    "https://webchat.botframework.com",
)
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        resp = httpx.get(_BOT_FRAMEWORK_OPENID_URL, timeout=10)
        resp.raise_for_status()
        jwks_uri = resp.json()["jwks_uri"]
        _jwks_client = PyJWKClient(jwks_uri)
    return _jwks_client


def verify_bot_token(token: str, app_id: str) -> None:
    """Validate Bot Framework JWT; raises HTTP 401 on failure."""
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization token")
    if not app_id:
        raise HTTPException(status_code=500, detail="TEAMS_APP_ID not configured")
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        jwt_decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=app_id,
            issuer="https://api.botframework.com",
        )
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Bot Framework token: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {exc}") from exc


# ─── Token cache ─────────────────────────────────────────────────────────────
_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


# ─── Schemas ─────────────────────────────────────────────────────────────────

class TeamsActivity(BaseModel):
    """Minimal Bot Framework Activity schema — fields we actually use."""
    type: str = ""
    id: str | None = None
    timestamp: str | None = None
    text: str | None = None
    from_: dict[str, Any] | None = Field(default=None, alias="from")
    recipient: dict[str, Any] | None = None
    conversation: dict[str, Any] | None = None
    channel_id: str | None = None
    service_url: str | None = None
    entities: list[dict[str, Any]] | None = None

    model_config = {"populate_by_name": True}


class TeamsWebhookResponse(BaseModel):
    status: str
    message: str | None = None


# ─── Bot Framework Auth ──────────────────────────────────────────────────────

async def _get_bot_token() -> str:
    """
    Obtain an OAuth2 token for the Bot Framework REST API.
    Caches the token until 60 s before expiry.
    """
    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["access_token"]

    if not TEAMS_APP_ID or not TEAMS_APP_SECRET:
        raise HTTPException(
            status_code=500,
            detail="TEAMS_APP_ID / TEAMS_APP_SECRET not configured",
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            BOT_FRAMEWORK_AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": TEAMS_APP_ID,
                "client_secret": TEAMS_APP_SECRET,
                "scope": BOT_FRAMEWORK_SCOPE,
            },
        )

    if resp.status_code != 200:
        log.error("bot_framework_token_failed", status=resp.status_code, body=resp.text)
        raise HTTPException(status_code=502, detail="Failed to obtain Bot Framework token")

    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)

    return data["access_token"]


# ─── Reply helper ────────────────────────────────────────────────────────────

async def _send_reply(service_url: str, conversation_id: str, activity_id: str, text: str) -> None:
    """
    Send a reply to a Teams conversation via Bot Framework REST API.
    """
    if not any(service_url.startswith(prefix) for prefix in ALLOWED_SERVICE_URL_PREFIXES):
        log.critical("teams_bot.ssrf_blocked", service_url=service_url)
        raise HTTPException(status_code=400, detail="Invalid service_url")

    token = await _get_bot_token()

    # Normalise service URL (must end with /)
    base = service_url.rstrip("/")
    url = f"{base}/v3/conversations/{conversation_id}/activities/{activity_id}"

    payload = {
        "type": "message",
        "text": text,
        "textFormat": "markdown",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )

    if resp.status_code not in (200, 201):
        log.error("teams_reply_failed", status=resp.status_code, url=url, body=resp.text[:500])


# ─── Business-only query engine (mirrors presentation_ask) ──────────────────

def _business_ask(query: str, conversation_id: str | None = None) -> str:
    """
    Run a business-only RAG query — identical filtering to /presentation/ask.
    Returns the answer text.
    """
    started_at = time.time()

    # Conversation history
    from app.db.conversation_store import get_store
    conversation_context = ""
    conv_store = None
    if conversation_id:
        conv_store = get_store("teams", conversation_id)
        conversation_context = conv_store.as_context_string()

    safe_source_types = _enforce_source_filter(None)

    interpreted = interpret_query(
        query=query,
        source_types=safe_source_types,
        source_names=None,
        date_from=None,
        date_to=None,
        mode="auto",
    )

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
            query=query,
            top_k=answer_match_limit,
            source_types=safe_source_types,
            source_names=None,
            date_from=None,
            date_to=None,
            prefetch_k=prefetch_k,
            question_type=interpreted.question_type,
        )

    # Defence-in-depth: strip any blocked sources
    matches = _validate_no_blocked_sources(matches)

    if not matches:
        return "Nie znalazlem wystarczajaco trafnego kontekstu biznesowego dla tego pytania."

    cleaned_matches, _ = cleanup_matches(
        matches,
        normalized_query=interpreted.normalized_query,
        top_k=min(8, answer_match_limit),
        max_per_document=2,
        min_score=None,
    )

    redacted_matches, _ = redact_matches(cleaned_matches)

    answer = answer_question(
        query=f"[KONTEKST SYSTEMOWY: {TEAMS_SYSTEM_ADDENDUM}]\n\n{query}",
        matches=redacted_matches,
        question_type=interpreted.question_type,
        analysis_depth=interpreted.analysis_depth,
        include_sources=False,
        answer_style="auto",
        answer_length="medium",
        allow_quotes=True,
        conversation_context=conversation_context,
    )

    # Save to conversation window
    if conv_store:
        conv_store.add("user", query)
        conv_store.add("assistant", answer)

    latency_ms = int((time.time() - started_at) * 1000)
    log.info("teams_bot_answered", latency_ms=latency_ms, matches=len(redacted_matches), question_type=interpreted.question_type)

    return answer


# ─── Mention handling ────────────────────────────────────────────────────────

def _strip_mention(text: str, entities: list[dict[str, Any]] | None) -> str:
    """
    Remove @mention tags from the incoming message text.
    Teams wraps mentions in <at>BotName</at> — strip those so the query
    is clean for the retriever.
    """
    if not entities:
        return text.strip()

    for entity in entities:
        if entity.get("type") == "mention":
            mentioned = entity.get("text", "")
            if mentioned:
                text = text.replace(mentioned, "")

    # Also strip any leftover <at>...</at> HTML tags
    import re
    text = re.sub(r"<at[^>]*>.*?</at>", "", text, flags=re.IGNORECASE)
    return text.strip()


# ─── Webhook endpoint ────────────────────────────────────────────────────────

@router.post("/webhook", response_model=TeamsWebhookResponse)
async def teams_webhook(request: Request) -> TeamsWebhookResponse:
    """
    Receive Bot Framework activities from Microsoft Teams.

    Handles:
      - message activities (text messages, @mentions)
      - conversationUpdate (bot added to team/chat — sends greeting)

    All queries are filtered through the BUSINESS-ONLY content filter.
    """
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    verify_bot_token(token, TEAMS_APP_ID)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    activity = TeamsActivity.model_validate(body)

    # ── Conversation update: greet when bot is added ─────────────────
    if activity.type == "conversationUpdate":
        members_added = body.get("membersAdded", [])
        bot_was_added = any(
            m.get("id") == (activity.recipient or {}).get("id")
            for m in members_added
        )
        if bot_was_added and activity.service_url and activity.conversation:
            greeting = (
                "Dzien dobry! Jestem **Gilbertus Albans**, asystent biznesowy "
                "Respect Energy.\n\n"
                "Mozesz mnie zapytac o:\n"
                "- Komunikacje firmowa (e-mail, Teams)\n"
                "- Dokumenty i arkusze\n"
                "- Notatki ze spotkan\n"
                "- Dane tradingowe\n\n"
                "_Wszystkie odpowiedzi opieraja sie wylacznie na danych "
                "biznesowych. Dane prywatne sa automatycznie odfiltrowywane._"
            )
            await _send_reply(
                service_url=activity.service_url,
                conversation_id=activity.conversation.get("id", ""),
                activity_id=activity.id or "",
                text=greeting,
            )
        return TeamsWebhookResponse(status="ok", message="conversationUpdate handled")

    # ── Message activity ─────────────────────────────────────────────
    if activity.type == "message":
        raw_text = activity.text or ""
        query = _strip_mention(raw_text, activity.entities)

        if not query:
            return TeamsWebhookResponse(status="ok", message="empty message ignored")

        log.info("teams_message_received", user=(activity.from_ or {}).get("name", "unknown"), query=query[:120])

        # Run the business-only RAG pipeline
        teams_conv_id = activity.conversation.get("id", "") if activity.conversation else None
        try:
            answer = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _business_ask(query, conversation_id=teams_conv_id)
            )
        except Exception as e:
            log.exception("teams_bot_business_ask_failed", error=str(e))
            answer = (
                "Przepraszam, wystapil blad podczas przetwarzania pytania. "
                "Sprobuj ponownie za chwile."
            )

        # Send reply via Bot Framework
        if activity.service_url and activity.conversation:
            await _send_reply(
                service_url=activity.service_url,
                conversation_id=activity.conversation.get("id", ""),
                activity_id=activity.id or "",
                text=answer,
            )

        return TeamsWebhookResponse(status="ok", message="reply sent")

    # ── Unknown activity type — acknowledge silently ─────────────────
    log.debug("teams_activity_ignored", activity_type=activity.type)
    return TeamsWebhookResponse(status="ok", message=f"ignored activity type: {activity.type}")
