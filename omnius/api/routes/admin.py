"""Omnius /admin/* endpoints — user management, config, sync, operator tasks."""
from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel

from omnius.api.rbac import require_permission
from omnius.core.permissions import can_manage_user
from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ── User Management ────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: str
    display_name: str
    role: str
    department: str | None = None


@router.post("/users")
@require_permission("users:manage:all")
async def create_user(request: Request, body: CreateUserRequest, user: dict = None):
    """Create a new Omnius user."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Check target role exists and caller can manage it
            cur.execute("SELECT id, level FROM omnius_roles WHERE name = %s", (body.role,))
            role = cur.fetchone()
            if not role:
                return {"status": "error", "error": f"Role '{body.role}' not found"}

            if not can_manage_user(user, role[1]):
                return {"status": "error", "error": "Cannot create user with higher role"}

            cur.execute("""
                INSERT INTO omnius_users (email, display_name, role_id, department)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (body.email, body.display_name, role[0], body.department))
            user_id = cur.fetchone()[0]
        conn.commit()

    log.info("user_created", id=user_id, email=body.email, role=body.role,
             by=user.get("email", user.get("api_key_name")))
    return {"status": "created", "user_id": user_id, "email": body.email, "role": body.role}


@router.get("/users")
@require_permission("users:manage:all")
async def list_users(request: Request, user: dict = None):
    """List all Omnius users."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.email, u.display_name, r.name, r.level,
                       u.department, u.is_active, u.created_at
                FROM omnius_users u
                JOIN omnius_roles r ON r.id = u.role_id
                ORDER BY r.level DESC, u.display_name
            """)
            return [
                {"id": r[0], "email": r[1], "name": r[2], "role": r[3],
                 "level": r[4], "department": r[5], "active": r[6],
                 "created": str(r[7])}
                for r in cur.fetchall()
            ]


# ── API Key Management ──────────────────────────────────────────────────────

class CreateApiKeyRequest(BaseModel):
    name: str
    role: str
    user_email: str | None = None


@router.post("/api-keys")
@require_permission("users:manage:all")
async def create_api_key(request: Request, body: CreateApiKeyRequest, user: dict = None):
    """Generate a new API key. Returns the key ONCE — store it securely."""
    raw_key = f"omnius_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM omnius_roles WHERE name = %s", (body.role,))
            role = cur.fetchone()
            if not role:
                return {"status": "error", "error": f"Role '{body.role}' not found"}

            user_id = None
            if body.user_email:
                cur.execute("SELECT id FROM omnius_users WHERE email = %s", (body.user_email,))
                u = cur.fetchone()
                if u:
                    user_id = u[0]

            cur.execute("""
                INSERT INTO omnius_api_keys (key_hash, name, role_id, user_id)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (key_hash, body.name, role[0], user_id))
            key_id = cur.fetchone()[0]
        conn.commit()

    log.info("api_key_created", id=key_id, name=body.name, role=body.role,
             by=user.get("email", user.get("api_key_name")))
    return {"status": "created", "key_id": key_id, "api_key": raw_key,
            "warning": "Store this key securely — it will not be shown again."}


# ── Config (pushed from Gilbertus) ─────────────────────────────────────────

class PushConfigRequest(BaseModel):
    key: str
    value: Any


@router.post("/config")
@require_permission("config:write:system")
async def push_config(request: Request, body: PushConfigRequest, user: dict = None):
    """Push config from Gilbertus or CEO. CEO/board subject to governance checks."""
    from omnius.core.governance import check_governance

    # Governance check for non-admin roles
    gov = check_governance(user, "update_config", {"key": body.key, "value": body.value})
    if not gov["allowed"]:
        return {"status": "denied", "reason": gov["reason"]}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO omnius_config (key, value, pushed_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET value = %s, pushed_by = %s, updated_at = NOW()
            """, (body.key, json.dumps(body.value),
                  user.get("email", user.get("api_key_name", "unknown")),
                  json.dumps(body.value),
                  user.get("email", user.get("api_key_name", "unknown"))))
        conn.commit()

    return {"status": "ok", "key": body.key}


@router.get("/config")
@require_permission("config:write:system")
async def get_config(request: Request, user: dict = None):
    """Get all config entries."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value, pushed_by, updated_at FROM omnius_config ORDER BY key")
            return [{"key": r[0], "value": r[1], "pushed_by": r[2], "updated_at": str(r[3])}
                    for r in cur.fetchall()]


# ── Operator Tasks ──────────────────────────────────────────────────────────

class CreateOperatorTaskRequest(BaseModel):
    title: str
    description: str | None = None
    assignee_email: str = "michal.schulta@re-fuels.com"


class UpdateOperatorTaskRequest(BaseModel):
    status: str
    result: str | None = None


@router.post("/operator-tasks")
@require_permission("dev:execute")
async def create_operator_task(request: Request, body: CreateOperatorTaskRequest, user: dict = None):
    """Create a task for the human operator (Michał)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO omnius_operator_tasks (title, description, source, assigned_to)
                VALUES (%s, %s, %s, (SELECT id FROM omnius_users WHERE email = %s))
                RETURNING id
            """, (body.title, body.description,
                  user.get("api_key_name", user.get("email", "unknown")),
                  body.assignee_email))
            task_id = cur.fetchone()[0]
        conn.commit()

    log.info("operator_task_created", id=task_id, title=body.title[:80],
             by=user.get("email", user.get("api_key_name")))
    return {"status": "created", "task_id": task_id}


@router.get("/operator-tasks")
@require_permission("dev:execute")
async def list_operator_tasks(request: Request, status: str = "pending", user: dict = None):
    """List operator tasks by status."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.id, t.title, t.description, t.source, t.status,
                       t.result, t.created_at, t.completed_at,
                       u.display_name
                FROM omnius_operator_tasks t
                LEFT JOIN omnius_users u ON u.id = t.assigned_to
                WHERE t.status = %s
                ORDER BY t.created_at DESC
            """, (status,))
            return [
                {"id": r[0], "title": r[1], "description": r[2], "source": r[3],
                 "status": r[4], "result": r[5], "created": str(r[6]),
                 "completed": str(r[7]) if r[7] else None, "assigned_to": r[8]}
                for r in cur.fetchall()
            ]


@router.patch("/operator-tasks/{task_id}")
@require_permission("dev:execute")
async def update_operator_task(request: Request, task_id: int,
                                body: UpdateOperatorTaskRequest, user: dict = None):
    """Update operator task status (e.g. mark as done)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE omnius_operator_tasks
                SET status = %s, result = %s,
                    completed_at = CASE WHEN %s = 'done' THEN NOW() ELSE NULL END
                WHERE id = %s
            """, (body.status, body.result, body.status, task_id))
            if cur.rowcount == 0:
                return {"status": "error", "error": "Task not found"}
        conn.commit()

    log.info("operator_task_updated", id=task_id, status=body.status,
             by=user.get("email", user.get("api_key_name")))
    return {"status": "ok", "task_id": task_id, "new_status": body.status}


# ── Feature proposals (governance-gated) ────────────────────────────────────

class ProposeFeatureRequest(BaseModel):
    title: str
    description: str
    expected_value: str  # what business value this generates


@router.post("/propose-feature")
@require_permission("config:write:system")
async def propose_feature(request: Request, body: ProposeFeatureRequest, user: dict = None):
    """Propose a new feature. CEO/board proposals are validated by Omnius for added value.
    Gilbertus_admin proposals bypass validation.

    Governance rules:
    - Features CAN be created if Omnius validates added value
    - Features CAN be improved
    - Features CANNOT be deleted or reduced (forbidden action)
    - Non-regression applies to all changes
    """
    from omnius.core.governance import check_governance, validate_value

    # Check governance — is this action type allowed?
    gov = check_governance(user, "create_feature", {"title": body.title})
    if not gov["allowed"]:
        return {"status": "denied", "reason": gov["reason"]}

    # Value check required for CEO/board (not for gilbertus_admin)
    if gov.get("requires_value_check"):
        proposal = f"Tytuł: {body.title}\nOpis: {body.description}\nOczekiwana wartość: {body.expected_value}"
        assessment = validate_value(proposal, user)

        if not assessment.get("approved"):
            # Create operator task to notify Gilbertus
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO omnius_operator_tasks
                            (title, description, source, status)
                        VALUES (%s, %s, %s, 'pending')
                    """, (
                        f"[REJECTED] Feature proposal: {body.title}",
                        f"Proposed by: {user.get('display_name')} ({user.get('role_name')})\n"
                        f"Description: {body.description}\n"
                        f"Expected value: {body.expected_value}\n"
                        f"Omnius assessment: {assessment.get('reasoning')}\n"
                        f"Value score: {assessment.get('value_score', 0)}",
                        "governance",
                    ))
                conn.commit()

            return {
                "status": "rejected",
                "value_score": assessment.get("value_score", 0),
                "reasoning": assessment.get("reasoning", ""),
                "message": "Propozycja odrzucona przez Omniusa. "
                           "Gilbertus został powiadomiony i może ręcznie zatwierdzić.",
            }

        # Approved — create operator task for implementation
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
                    f"[APPROVED] New feature: {body.title}",
                    f"Proposed by: {user.get('display_name')} ({user.get('role_name')})\n"
                    f"Description: {body.description}\n"
                    f"Expected value: {body.expected_value}\n"
                    f"Omnius assessment: {assessment.get('reasoning')}\n"
                    f"Value score: {assessment.get('value_score', 0)}",
                    f"governance:{user.get('email', 'unknown')}",
                ))
                task_id = cur.fetchone()[0]
            conn.commit()

        return {
            "status": "approved",
            "task_id": task_id,
            "value_score": assessment.get("value_score", 0),
            "reasoning": assessment.get("reasoning", ""),
            "message": f"Feature zatwierdzony. Task #{task_id} przypisany do operatora.",
        }

    # Gilbertus_admin — direct approval
    return {"status": "approved", "message": "Gilbertus admin — governance bypass"}


# ── Sync trigger ────────────────────────────────────────────────────────────

class TriggerSyncRequest(BaseModel):
    source: str = "all"  # teams, sharepoint, email, all


@router.post("/sync")
@require_permission("sync:manage")
async def trigger_sync(request: Request, body: TriggerSyncRequest, user: dict = None):
    """Trigger M365 data sync. Returns immediately, sync runs in background."""
    # TODO: implement actual sync trigger (subprocess or task queue)
    log.info("sync_triggered", source=body.source,
             by=user.get("email", user.get("api_key_name")))
    return {"status": "queued", "source": body.source}


# ── Audit log ───────────────────────────────────────────────────────────────

@router.get("/audit")
@require_permission("config:write:system")
async def get_audit_log(request: Request, limit: int = 50, user: dict = None):
    """Get recent audit log entries."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT al.id, u.email, al.action, al.resource,
                       al.result_status, al.ip_address, al.created_at
                FROM omnius_audit_log al
                LEFT JOIN omnius_users u ON u.id = al.user_id
                ORDER BY al.created_at DESC
                LIMIT %s
            """, (limit,))
            return [
                {"id": r[0], "user": r[1], "action": r[2], "resource": r[3],
                 "result": r[4], "ip": str(r[5]) if r[5] else None,
                 "at": str(r[6])}
                for r in cur.fetchall()
            ]
