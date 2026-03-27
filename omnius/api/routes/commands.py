"""Omnius /commands/* endpoints — RBAC-protected corporate actions."""
from __future__ import annotations

import os

import httpx
import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from omnius.api.rbac import require_permission

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/commands", tags=["commands"])

# Graph API config (REF tenant)
GRAPH_TENANT_ID = os.getenv("OMNIUS_AZURE_TENANT_ID", "")
GRAPH_CLIENT_ID = os.getenv("OMNIUS_GRAPH_CLIENT_ID", "")
GRAPH_CLIENT_SECRET = os.getenv("OMNIUS_GRAPH_CLIENT_SECRET", "")


async def _get_graph_token() -> str:
    """Get Microsoft Graph API token for application permissions."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{GRAPH_TENANT_ID}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": GRAPH_CLIENT_ID,
                "client_secret": GRAPH_CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


# ── Send Email ──────────────────────────────────────────────────────────────

class SendEmailRequest(BaseModel):
    to: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    cc: list[str] | None = None


@router.post("/send_email")
@require_permission("commands:email")
async def send_email(request: Request, body: SendEmailRequest, user: dict = None):
    """Send email via Microsoft Graph API."""
    try:
        token = await _get_graph_token()
        sender = user.get("email", "noreply@re-fuels.com")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
                headers={"Authorization": f"Bearer {token}"},
                json={"message": {
                    "subject": body.subject,
                    "body": {"contentType": "Text", "content": body.body},
                    "toRecipients": [{"emailAddress": {"address": body.to}}],
                    "ccRecipients": [{"emailAddress": {"address": cc}} for cc in (body.cc or [])],
                }},
            )
            resp.raise_for_status()

        log.info("email_sent", by=user.get("email"), to=body.to, subject=body.subject[:80])
        return {"status": "sent", "to": body.to}
    except Exception as e:
        log.error("email_failed", error=str(e))
        return {"status": "error", "error": "Operation failed. Check logs for details."}


# ── Create Ticket ───────────────────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    title: str
    description: str = ""
    assignee: str | None = None
    priority: str = "medium"


@router.post("/create_ticket")
@require_permission("commands:ticket")
async def create_ticket(request: Request, body: CreateTicketRequest, user: dict = None):
    """Create a task/ticket (stored in operator_tasks for now)."""
    from omnius.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO omnius_operator_tasks (title, description, source, assigned_to)
                VALUES (%s, %s, %s, (SELECT id FROM omnius_users WHERE email = %s))
                RETURNING id
            """, (body.title, body.description,
                  user.get("email", "unknown"),
                  body.assignee or "michal.schulta@re-fuels.com"))
            ticket_id = cur.fetchone()[0]
        conn.commit()

    log.info("ticket_created", id=ticket_id, by=user.get("email"), title=body.title[:80])
    return {"status": "created", "ticket_id": ticket_id}


# ── Schedule Meeting ────────────────────────────────────────────────────────

class ScheduleMeetingRequest(BaseModel):
    subject: str
    attendees: list[str]
    start: str  # ISO 8601
    end: str
    body: str = ""


@router.post("/schedule_meeting")
@require_permission("commands:meeting")
async def schedule_meeting(request: Request, body: ScheduleMeetingRequest, user: dict = None):
    """Schedule meeting via Microsoft Graph API."""
    try:
        token = await _get_graph_token()
        organizer = user.get("email", "")

        event_data = {
            "subject": body.subject,
            "body": {"contentType": "Text", "content": body.body},
            "start": {"dateTime": body.start, "timeZone": "Europe/Warsaw"},
            "end": {"dateTime": body.end, "timeZone": "Europe/Warsaw"},
            "attendees": [
                {"emailAddress": {"address": a}, "type": "required"}
                for a in body.attendees
            ],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://graph.microsoft.com/v1.0/users/{organizer}/events",
                headers={"Authorization": f"Bearer {token}"},
                json=event_data,
            )
            resp.raise_for_status()

        log.info("meeting_scheduled", by=user.get("email"), subject=body.subject[:80])
        return {"status": "scheduled", "subject": body.subject}
    except Exception as e:
        log.error("meeting_failed", error=str(e))
        return {"status": "error", "error": "Operation failed. Check logs for details."}


# ── Assign Task ─────────────────────────────────────────────────────────────

class AssignTaskRequest(BaseModel):
    description: str
    assignee: str
    deadline: str | None = None
    priority: str = "medium"


@router.post("/assign_task")
@require_permission("commands:task")
async def assign_task(request: Request, body: AssignTaskRequest, user: dict = None):
    """Assign task to a user (stored in operator_tasks)."""
    from omnius.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO omnius_operator_tasks (title, description, source, assigned_to)
                VALUES (%s, %s, %s, (SELECT id FROM omnius_users WHERE email = %s))
                RETURNING id
            """, (f"[{body.priority}] {body.description[:100]}",
                  body.description, user.get("email", "unknown"), body.assignee))
            task_id = cur.fetchone()[0]
        conn.commit()

    log.info("task_assigned", id=task_id, by=user.get("email"), to=body.assignee)
    return {"status": "assigned", "task_id": task_id}
