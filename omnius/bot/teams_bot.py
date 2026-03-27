"""Omnius Teams Bot — RBAC-aware corporate AI chat in Microsoft Teams.

Receives Bot Framework webhook, identifies user from Azure AD,
checks RBAC permissions, and responds with data from Omnius.

Operator (Michał) gets task notifications and can update task status.
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from omnius.api.rbac import audit_log
from omnius.core.permissions import allowed_classifications, has_permission
from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/teams", tags=["teams"])

# Bot Framework config
TEAMS_APP_ID = os.getenv("OMNIUS_TEAMS_APP_ID", "")
TEAMS_APP_SECRET = os.getenv("OMNIUS_TEAMS_APP_SECRET", "")
TEAMS_TENANT_ID = os.getenv("OMNIUS_AZURE_TENANT_ID", "")
COMPANY_NAME = os.getenv("OMNIUS_COMPANY_NAME", "Respect Energy Fuels")

BOT_FRAMEWORK_AUTH_URL = (
    f"https://login.microsoftonline.com/{TEAMS_TENANT_ID}/oauth2/v2.0/token"
    if TEAMS_TENANT_ID
    else "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
)

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}
_token_lock = asyncio.Lock()

SYSTEM_PROMPT = (
    "Jesteś Omnius, korporacyjny asystent AI dla {company}. "
    "Użytkownik: {user_name} ({role}). "
    "Odpowiadaj profesjonalnie, konkretnie i na podstawie dostarczonych danych firmowych. "
    "Jeśli nie masz danych — powiedz to wprost. Formatuj w Markdown."
)


class TeamsActivity(BaseModel):
    type: str = ""
    id: str | None = None
    text: str | None = None
    from_: dict[str, Any] | None = Field(default=None, alias="from")
    recipient: dict[str, Any] | None = None
    conversation: dict[str, Any] | None = None
    service_url: str | None = None
    entities: list[dict[str, Any]] | None = None

    model_config = {"populate_by_name": True}


# ── Bot Framework Auth ──────────────────────────────────────────────────────

async def _get_bot_token() -> str:
    now = time.time()
    async with _token_lock:
        if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
            return _token_cache["access_token"]

        if not TEAMS_APP_ID or not TEAMS_APP_SECRET:
            raise HTTPException(status_code=500, detail="Teams Bot not configured")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                BOT_FRAMEWORK_AUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": TEAMS_APP_ID,
                    "client_secret": TEAMS_APP_SECRET,
                    "scope": "https://api.botframework.com/.default",
                },
            )

        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Bot Framework token failed")

        data = resp.json()
        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 3600)
        return data["access_token"]


async def _send_reply(service_url: str, conversation_id: str,
                      activity_id: str, text: str) -> None:
    token = await _get_bot_token()
    base = service_url.rstrip("/")
    url = f"{base}/v3/conversations/{conversation_id}/activities/{activity_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            json={"type": "message", "text": text, "textFormat": "markdown"},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )

    if resp.status_code not in (200, 201):
        log.error("teams_reply_failed", status=resp.status_code, body=resp.text[:300])


# ── Mention handling ────────────────────────────────────────────────────────

def _strip_mention(text: str, entities: list[dict[str, Any]] | None) -> str:
    if not entities:
        return text.strip()

    for entity in entities:
        if entity.get("type") == "mention":
            mentioned = entity.get("text", "")
            if mentioned:
                text = text.replace(mentioned, "")

    text = re.sub(r"<at[^>]*>.*?</at>", "", text, flags=re.IGNORECASE)
    return text.strip()


# ── Operator command handling ───────────────────────────────────────────────

def _handle_feature_proposal(text: str, user: dict) -> str | None:
    """Handle feature proposals from CEO/board via Teams.

    Triggers: 'nowa funkcjonalność:', 'new feature:', 'proponuję:', 'chcę dodać:'
    """
    text_lower = text.lower().strip()
    triggers = ["nowa funkcjonalność:", "new feature:", "proponuję:", "chcę dodać:",
                "dodaj funkcję:", "potrzebuję:"]

    matched = None
    for t in triggers:
        if text_lower.startswith(t):
            matched = t
            break

    if not matched:
        return None

    proposal = text[len(matched):].strip()
    if not proposal:
        return "Podaj opis funkcjonalności, np.: `nowa funkcjonalność: dashboard z KPI handlowymi`"

    from omnius.core.governance import check_governance, validate_value

    gov = check_governance(user, "create_feature", {"title": proposal[:100]})
    if not gov["allowed"]:
        return f"Propozycja zablokowana: {gov['reason']}"

    if gov.get("requires_value_check"):
        assessment = validate_value(proposal, user)

        if not assessment.get("approved"):
            return (
                f"**Propozycja odrzucona przez Omniusa.**\n\n"
                f"Ocena wartości: {assessment.get('value_score', 0):.1f}/1.0\n"
                f"Uzasadnienie: {assessment.get('reasoning', 'brak')}\n\n"
                f"_Gilbertus został powiadomiony i może ręcznie zatwierdzić._"
            )

        # Create operator task
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO omnius_operator_tasks
                        (title, description, source, assigned_to, status)
                    VALUES (%s, %s, %s,
                            (SELECT id FROM omnius_users WHERE email = 'michal.schulta@re-fuels.com'),
                            'pending')
                    RETURNING id
                """, (
                    f"[APPROVED] {proposal[:100]}",
                    f"Proposed by: {user.get('display_name')} ({user.get('role_name')})\n{proposal}",
                    f"governance:{user.get('email', 'unknown')}",
                ))
                task_id = cur.fetchone()[0]
            conn.commit()

        return (
            f"**Feature zatwierdzony!**\n\n"
            f"Ocena wartości: {assessment.get('value_score', 0):.1f}/1.0\n"
            f"Uzasadnienie: {assessment.get('reasoning', '')}\n\n"
            f"Task **#{task_id}** przypisany do operatora."
        )

    return None


def _handle_operator_command(text: str, user: dict) -> str | None:
    """Handle operator-specific commands: done #N, status, tasks."""
    text_lower = text.lower().strip()

    # done #N [result]
    done_match = re.match(r'done\s+#?(\d+)\s*(.*)', text_lower, re.DOTALL)
    if done_match:
        task_id = int(done_match.group(1))
        result = done_match.group(2).strip() or "Done"
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omnius_operator_tasks
                    SET status = 'done', result = %s, completed_at = NOW()
                    WHERE id = %s AND assigned_to = %s
                      AND status IN ('pending', 'in_progress')
                """, (result, task_id, user.get("user_id")))
                if cur.rowcount == 0:
                    return f"Task #{task_id} nie znaleziony lub już zakończony."
            conn.commit()
        return f"Task #{task_id} oznaczony jako done."

    # tasks / moje zadania
    if text_lower in ("tasks", "moje zadania", "zadania"):
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, title, source, status, created_at
                    FROM omnius_operator_tasks
                    WHERE assigned_to = %s AND status IN ('pending', 'in_progress')
                    ORDER BY created_at DESC LIMIT 10
                """, (user.get("user_id"),))
                tasks = cur.fetchall()

        if not tasks:
            return "Brak aktywnych zadań."

        lines = ["**Twoje zadania:**"]
        for t in tasks:
            emoji = {"pending": "⏳", "in_progress": "🔄"}.get(t[3], "")
            lines.append(f"{emoji} **#{t[0]}** {t[1]} _(od: {t[2]})_")
        lines.append("\n_Odpowiedz `done #N [wynik]` aby zakończyć zadanie._")
        return "\n".join(lines)

    return None


# ── RAG query ───────────────────────────────────────────────────────────────

def _omnius_ask(query: str, user: dict) -> str:
    """Run RBAC-aware RAG query against corporate data."""
    import os
    from anthropic import Anthropic

    started_at = time.time()
    classifications = allowed_classifications(user.get("role_name", "specialist"))

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.content, d.title, d.source_type
                FROM omnius_chunks c
                JOIN omnius_documents d ON d.id = c.document_id
                WHERE c.classification = ANY(%s)
                  AND to_tsvector('simple', c.content) @@ plainto_tsquery('simple', %s)
                ORDER BY ts_rank(to_tsvector('simple', c.content),
                                 plainto_tsquery('simple', %s)) DESC
                LIMIT 10
            """, (classifications, query, query))
            matches = cur.fetchall()

    if not matches:
        return "Nie znalazłem wystarczających danych dla tego pytania."

    context = "\n\n".join([
        f"--- [{r[2]}] {r[1] or 'Untitled'} ---\n{r[0][:2000]}"
        for r in matches
    ])

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=os.getenv("OMNIUS_LLM_MODEL", "claude-haiku-4-5"),
        max_tokens=800,
        system=SYSTEM_PROMPT.format(
            company=COMPANY_NAME,
            user_name=user.get("display_name", "Unknown"),
            role=user.get("role_name", "unknown"),
        ),
        messages=[{
            "role": "user",
            "content": f"Kontekst:\n\n{context}\n\n---\nPytanie: {query}",
        }],
    )

    answer = response.content[0].text
    log.info("teams_ask", user=user.get("email"), query=query[:100],
             matches=len(matches), ms=int((time.time() - started_at) * 1000))
    return answer


# ── Webhook ─────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def teams_webhook(request: Request):
    """Receive Bot Framework activities from Microsoft Teams."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    activity = TeamsActivity.model_validate(body)

    # Conversation update — greet
    if activity.type == "conversationUpdate":
        members_added = body.get("membersAdded", [])
        bot_added = any(
            m.get("id") == (activity.recipient or {}).get("id")
            for m in members_added
        )
        if bot_added and activity.service_url and activity.conversation:
            greeting = (
                f"Dzień dobry! Jestem **Omnius**, korporacyjny asystent AI "
                f"dla **{COMPANY_NAME}**.\n\n"
                f"Możesz mnie zapytać o dane firmowe, dokumenty, komunikację "
                f"i projekty.\n\n"
                f"_Twój dostęp zależy od Twojej roli w organizacji._"
            )
            await _send_reply(
                activity.service_url,
                activity.conversation.get("id", ""),
                activity.id or "",
                greeting,
            )
        return {"status": "ok"}

    # Message
    if activity.type == "message":
        raw_text = activity.text or ""
        query = _strip_mention(raw_text, activity.entities)

        if not query:
            return {"status": "ok"}

        # Identify user from Teams UPN
        from_info = activity.from_ or {}
        user_upn = from_info.get("aadObjectId", "")
        user_name = from_info.get("name", "Unknown")

        # Try to find user in Omnius
        try:
            # Look up by Azure AD OID first, then by name match
            user = _resolve_teams_user(user_upn, user_name)
        except HTTPException:
            await _send_reply(
                activity.service_url or "",
                (activity.conversation or {}).get("id", ""),
                activity.id or "",
                "Nie masz dostępu do Omniusa. Skontaktuj się z administratorem.",
            )
            return {"status": "denied"}

        audit_log(user, "teams_message", resource=query[:200])

        # Check for feature proposals (CEO/board governance-gated)
        if user.get("role_name") in ("ceo", "board"):
            feature_result = _handle_feature_proposal(query, user)
            if feature_result:
                await _send_reply(
                    activity.service_url or "",
                    (activity.conversation or {}).get("id", ""),
                    activity.id or "",
                    feature_result,
                )
                return {"status": "ok"}

        # Check for operator commands (operator can ONLY use task commands)
        if user.get("role_name") == "operator" or has_permission(user, "dev:execute"):
            op_result = _handle_operator_command(query, user)
            if op_result:
                await _send_reply(
                    activity.service_url or "",
                    (activity.conversation or {}).get("id", ""),
                    activity.id or "",
                    op_result,
                )
                return {"status": "ok"}

            # Operator can only use task commands — no RAG access
            if user.get("role_name") == "operator":
                await _send_reply(
                    activity.service_url or "",
                    (activity.conversation or {}).get("id", ""),
                    activity.id or "",
                    "Jako operator masz dostęp tylko do zadań. "
                    "Użyj: `tasks`, `done #N [wynik]`.\n"
                    "Nie masz dostępu do danych biznesowych.",
                )
                return {"status": "ok"}

        # RAG query (business roles only)
        try:
            answer = _omnius_ask(query, user)
        except Exception as e:
            log.exception("teams_ask_failed", error=str(e))
            answer = "Przepraszam, wystąpił błąd. Spróbuj ponownie za chwilę."

        if activity.service_url and activity.conversation:
            await _send_reply(
                activity.service_url,
                activity.conversation.get("id", ""),
                activity.id or "",
                answer,
            )

        return {"status": "ok"}

    return {"status": "ok"}


def _resolve_teams_user(aad_oid: str, display_name: str) -> dict:
    """Resolve Teams user to Omnius user by Azure AD OID or email."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Try by Azure AD OID
            if aad_oid:
                cur.execute("""
                    SELECT u.id, u.email, u.display_name, r.name, r.level
                    FROM omnius_users u
                    JOIN omnius_roles r ON r.id = u.role_id
                    WHERE u.azure_ad_oid = %s AND u.is_active = TRUE
                """, (aad_oid,))
                row = cur.fetchone()
                if row:
                    perms = _load_perms(cur, row[3])
                    return {"user_id": row[0], "email": row[1], "display_name": row[2],
                            "role_name": row[3], "role_level": row[4], "permissions": perms}

            # Try by display name (fuzzy)
            cur.execute("""
                SELECT u.id, u.email, u.display_name, r.name, r.level
                FROM omnius_users u
                JOIN omnius_roles r ON r.id = u.role_id
                WHERE u.is_active = TRUE AND u.display_name ILIKE %s
            """, (f"%{display_name}%",))
            row = cur.fetchone()
            if row:
                # Update azure_ad_oid for future lookups
                if aad_oid:
                    cur.execute("UPDATE omnius_users SET azure_ad_oid = %s WHERE id = %s",
                                (aad_oid, row[0]))
                    conn.commit()
                perms = _load_perms(cur, row[3])
                return {"user_id": row[0], "email": row[1], "display_name": row[2],
                        "role_name": row[3], "role_level": row[4], "permissions": perms}

    raise HTTPException(status_code=403, detail="User not registered")


def _load_perms(cur, role_name: str) -> set[str]:
    cur.execute("""
        SELECT p.permission FROM omnius_permissions p
        JOIN omnius_roles r ON r.id = p.role_id WHERE r.name = %s
    """, (role_name,))
    return {row[0] for row in cur.fetchall()}
