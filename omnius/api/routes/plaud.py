"""Plaud webhook + management endpoints for Omnius.

Per-user Plaud integration:
- POST /webhook/plaud/{user_id} — receive webhook from Plaud (no auth, HMAC verified)
- POST /api/v1/plaud/config — configure Plaud credentials (operator/CEO)
- GET  /api/v1/plaud/recordings — list user's recordings
- POST /api/v1/plaud/rules — set classification rules
- POST /api/v1/plaud/sync — trigger manual sync
"""
from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from omnius.api.rbac import require_permission
from omnius.db.postgres import get_pg_connection
from omnius.sync.plaud_sync import (
    parse_plaud_payload,
    store_recording,
    sync_user_plaud,
    verify_webhook_signature,
)

log = structlog.get_logger(__name__)

router = APIRouter(tags=["plaud"])
webhook_router = APIRouter(tags=["plaud-webhook"])


# ── Webhook (no auth — verified by HMAC signature) ─────────────────────────

@webhook_router.post("/webhook/plaud/{user_id}")
async def plaud_webhook(request: Request, user_id: int):
    """Receive Plaud webhook for a specific user. HMAC-verified, no auth token needed."""
    body = await request.body()

    # Load user's webhook secret
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pc.webhook_secret, u.display_name
                FROM omnius_plaud_config pc
                JOIN omnius_users u ON u.id = pc.user_id
                WHERE pc.user_id = %s
            """, (user_id,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not configured for Plaud")

    secret, user_name = row

    # Verify HMAC signature
    signature = request.headers.get("X-Plaud-Signature", "")
    if secret and not verify_webhook_signature(body, signature, secret):
        log.warning("plaud_webhook_signature_failed", user_id=user_id)
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    parsed = parse_plaud_payload(data)
    result = store_recording(user_id, parsed, source="plaud_webhook")

    log.info("plaud_webhook_received", user_id=user_id, user=user_name,
             title=parsed["title"][:80], status=result["status"])

    return result


# ── Plaud config management ────────────────────────────────────────────────

class PlaudConfigRequest(BaseModel):
    user_email: str
    plaud_auth_token: str | None = None
    webhook_secret: str | None = None
    device_name: str = "Plaud Pin S"
    auto_sync: bool = True


@router.post("/plaud/config")
@require_permission("sync:credentials")
async def configure_plaud(request: Request, body: PlaudConfigRequest, user: dict = None):
    """Configure Plaud credentials for a user. Operator or CEO only."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Find target user
            cur.execute("SELECT id FROM omnius_users WHERE email = %s", (body.user_email,))
            target = cur.fetchone()
            if not target:
                return {"status": "error", "error": "User not found"}

            target_id = target[0]

            cur.execute("""
                INSERT INTO omnius_plaud_config
                    (user_id, plaud_auth_token, webhook_secret, device_name, auto_sync)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    plaud_auth_token = COALESCE(EXCLUDED.plaud_auth_token, omnius_plaud_config.plaud_auth_token),
                    webhook_secret = COALESCE(EXCLUDED.webhook_secret, omnius_plaud_config.webhook_secret),
                    device_name = EXCLUDED.device_name,
                    auto_sync = EXCLUDED.auto_sync,
                    updated_at = NOW()
            """, (target_id, body.plaud_auth_token, body.webhook_secret,
                  body.device_name, body.auto_sync))
        conn.commit()

    log.info("plaud_config_updated", target=body.user_email,
             by=user.get("email", user.get("api_key_name")))
    return {"status": "ok", "user": body.user_email, "device": body.device_name}


# ── Classification rules ───────────────────────────────────────────────────

class AudioRuleRequest(BaseModel):
    user_email: str
    rule_type: str = Field(..., pattern="^(keyword|participant|time_range|default)$")
    pattern: str
    classification: str = Field(default="personal", pattern="^(personal|corporate|confidential|ceo_only)$")


@router.post("/plaud/rules")
@require_permission("config:write:system")
async def add_audio_rule(request: Request, body: AudioRuleRequest, user: dict = None):
    """Add classification rule for a user's audio recordings."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM omnius_users WHERE email = %s", (body.user_email,))
            target = cur.fetchone()
            if not target:
                return {"status": "error", "error": "User not found"}

            cur.execute("""
                INSERT INTO omnius_audio_rules (user_id, rule_type, pattern, classification)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (target[0], body.rule_type, body.pattern, body.classification))
            rule_id = cur.fetchone()[0]
        conn.commit()

    return {"status": "created", "rule_id": rule_id}


@router.get("/plaud/rules")
@require_permission("config:write:system")
async def list_audio_rules(request: Request, user_email: str | None = None, user: dict = None):
    """List classification rules for audio recordings."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if user_email:
                cur.execute("""
                    SELECT r.id, u.email, r.rule_type, r.pattern, r.classification
                    FROM omnius_audio_rules r
                    JOIN omnius_users u ON u.id = r.user_id
                    WHERE u.email = %s ORDER BY r.id
                """, (user_email,))
            else:
                cur.execute("""
                    SELECT r.id, u.email, r.rule_type, r.pattern, r.classification
                    FROM omnius_audio_rules r
                    JOIN omnius_users u ON u.id = r.user_id
                    ORDER BY u.email, r.id
                """)
            return [
                {"id": r[0], "user": r[1], "type": r[2], "pattern": r[3], "classification": r[4]}
                for r in cur.fetchall()
            ]


# ── Manual sync trigger ────────────────────────────────────────────────────

@router.post("/plaud/sync")
@require_permission("sync:manage")
async def trigger_plaud_sync(request: Request, user_email: str | None = None, user: dict = None):
    """Trigger Plaud sync for one user or all configured users."""
    if user_email:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM omnius_users WHERE email = %s", (user_email,))
                target = cur.fetchone()
                if not target:
                    return {"status": "error", "error": "User not found"}
                result = sync_user_plaud(target[0])
                return {"status": "ok", "user": user_email, **result}
    else:
        from omnius.sync.plaud_sync import sync_all_users
        results = sync_all_users()
        return {"status": "ok", "users": results}


# ── User's own recordings ──────────────────────────────────────────────────

@router.get("/plaud/recordings")
@require_permission("data:read:own")
async def list_recordings(request: Request, limit: int = 20, user: dict = None):
    """List current user's Plaud recordings."""
    user_id = user.get("user_id")
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.classification, d.imported_at, d.metadata
                FROM omnius_documents d
                WHERE d.source_type = 'audio_transcript'
                  AND d.owner_user_id = %s
                ORDER BY d.imported_at DESC
                LIMIT %s
            """, (user_id, limit))
            return [
                {"id": r[0], "title": r[1], "classification": r[2],
                 "imported_at": str(r[3]), "metadata": r[4]}
                for r in cur.fetchall()
            ]
