"""
Action Item Pipeline — Gilbertus proposes actions, Sebastian approves via WhatsApp.

Flow:
1. Alert/Brief/Analysis detects something actionable
2. Gilbertus creates a proposed action (pending approval)
3. Sends proposal to Sebastian via WhatsApp
4. Sebastian replies: "tak" / "nie" / "zmień X"
5. On approval, Gilbertus executes via Graph API or Omnius command
6. Logs action + outcome

WhatsApp keywords:
  "approve #123" or "tak #123" — approve action
  "reject #123" or "nie #123" — reject action
  "edit #123: [new text]" — modify and approve
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "+48505441635")


# ================================================================
# Database
# ================================================================

def _ensure_table():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS action_items (
                    id BIGSERIAL PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    draft_params JSONB,
                    source TEXT,
                    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'executed', 'failed')),
                    proposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    decided_at TIMESTAMPTZ,
                    executed_at TIMESTAMPTZ,
                    result TEXT,
                    decided_by TEXT DEFAULT 'sebastian'
                )
            """)
        conn.commit()


def propose_action(
    action_type: str,
    description: str,
    draft_params: dict | None = None,
    source: str = "gilbertus",
    notify: bool = True,
) -> int:
    """Create a proposed action and optionally notify Sebastian."""
    _ensure_table()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO action_items (action_type, description, draft_params, source)
                   VALUES (%s, %s, %s::jsonb, %s) RETURNING id""",
                (action_type, description, json.dumps(draft_params or {}, default=str), source),
            )
            action_id = cur.fetchall()[0][0]
        conn.commit()

    if notify:
        _notify_proposal(action_id, action_type, description, draft_params)

    return action_id


def _notify_proposal(action_id: int, action_type: str, description: str, params: dict | None):
    """Send action proposal to WhatsApp."""
    msg_parts = [
        f"🔔 *Propozycja akcji #{action_id}*",
        f"Typ: {action_type}",
        "",
        description[:500],
    ]

    if params:
        if params.get("to"):
            msg_parts.append(f"\nDo: {params['to']}")
        if params.get("subject"):
            msg_parts.append(f"Temat: {params['subject']}")
        if params.get("body"):
            msg_parts.append(f"\n---\n{params['body'][:300]}\n---")

    msg_parts.extend([
        "",
        "Odpowiedz:",
        f"  *tak #{action_id}* — zatwierdź",
        f"  *nie #{action_id}* — odrzuć",
        f"  *edit #{action_id}: [zmiany]* — zmień i zatwierdź",
    ])

    _send_whatsapp("\n".join(msg_parts))


def approve_action(action_id: int, edit_text: str | None = None) -> dict[str, Any]:
    """Approve and execute an action."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT action_type, description, draft_params, status FROM action_items WHERE id = %s",
                (action_id,),
            )
            rows = cur.fetchall()
            if not rows:
                return {"error": f"Action #{action_id} not found"}

            action_type, description, params, status = rows[0]
            if status != "pending":
                return {"error": f"Action #{action_id} is already {status}"}

            params = params or {}

            # Apply edits if provided
            if edit_text:
                description = edit_text
                params["edited"] = True

            # Mark as approved
            cur.execute(
                "UPDATE action_items SET status = 'approved', decided_at = NOW() WHERE id = %s",
                (action_id,),
            )
        conn.commit()

    # Execute
    result = _execute_action(action_id, action_type, description, params)
    return result


def reject_action(action_id: int) -> dict[str, Any]:
    """Reject an action."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE action_items SET status = 'rejected', decided_at = NOW() WHERE id = %s AND status = 'pending'",
                (action_id,),
            )
            if cur.rowcount == 0:
                return {"error": f"Action #{action_id} not found or not pending"}
        conn.commit()
    return {"action_id": action_id, "status": "rejected"}


def _execute_action(action_id: int, action_type: str, description: str, params: dict) -> dict[str, Any]:
    """Execute an approved action."""
    try:
        if action_type == "send_email":
            result = _exec_send_email(params)
        elif action_type == "create_ticket":
            result = _exec_create_ticket(params)
        elif action_type == "schedule_meeting":
            result = _exec_schedule_meeting(params)
        elif action_type == "send_whatsapp":
            result = _exec_send_whatsapp(params)
        elif action_type == "omnius_command":
            result = _exec_omnius_command(params)
        else:
            result = {"status": "unknown_type", "note": f"Manual execution needed: {description}"}

        # Mark as executed
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE action_items SET status = 'executed', executed_at = NOW(), result = %s WHERE id = %s",
                    (json.dumps(result, default=str), action_id),
                )
            conn.commit()

        _send_whatsapp(f"✅ *Akcja #{action_id} wykonana*\n{result.get('status', 'ok')}")
        return {"action_id": action_id, "status": "executed", "result": result}

    except Exception as e:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE action_items SET status = 'failed', result = %s WHERE id = %s",
                    (str(e), action_id),
                )
            conn.commit()
        _send_whatsapp(f"❌ *Akcja #{action_id} failed:* {str(e)[:200]}")
        return {"action_id": action_id, "status": "failed", "error": str(e)}


# ================================================================
# Executors
# ================================================================

def _exec_send_email(params: dict) -> dict:
    """Send email via Graph API."""
    from app.ingestion.graph_api.auth import get_access_token
    import requests

    token = get_access_token()
    user_id = os.getenv("MS_GRAPH_USER_ID")
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/sendMail"

    email = {
        "message": {
            "subject": params.get("subject", "(no subject)"),
            "body": {"contentType": "Text", "content": params.get("body", "")},
            "toRecipients": [{"emailAddress": {"address": params["to"]}}],
        }
    }
    if params.get("cc"):
        email["message"]["ccRecipients"] = [{"emailAddress": {"address": cc}} for cc in params["cc"]]

    resp = requests.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                         json=email, timeout=30)
    resp.raise_for_status()
    return {"status": "sent", "to": params["to"], "subject": params.get("subject")}


def _exec_create_ticket(params: dict) -> dict:
    """Create ticket in Omnius."""
    from app.omnius.client import get_omnius
    tenant = params.get("tenant", "reh")
    client = get_omnius(tenant)
    return client.create_ticket(
        title=params.get("title", ""),
        description=params.get("description", ""),
        assignee=params.get("assignee"),
        priority=params.get("priority", "medium"),
    )


def _exec_schedule_meeting(params: dict) -> dict:
    """Schedule meeting via Graph API."""
    from app.ingestion.graph_api.auth import get_access_token
    import requests

    token = get_access_token()
    user_id = os.getenv("MS_GRAPH_USER_ID")
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/events"

    event = {
        "subject": params.get("subject", "Meeting"),
        "body": {"contentType": "Text", "content": params.get("body", "")},
        "start": {"dateTime": params["start"], "timeZone": "Europe/Warsaw"},
        "end": {"dateTime": params["end"], "timeZone": "Europe/Warsaw"},
        "attendees": [{"emailAddress": {"address": a}, "type": "required"} for a in params.get("attendees", [])],
    }

    resp = requests.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                         json=event, timeout=30)
    resp.raise_for_status()
    return {"status": "created", "subject": params.get("subject")}


def _exec_send_whatsapp(params: dict) -> dict:
    _send_whatsapp(params.get("message", ""))
    return {"status": "sent"}


def _exec_omnius_command(params: dict) -> dict:
    from app.omnius.client import get_omnius
    tenant = params.get("tenant", "reh")
    command = params.get("command", "")
    client = get_omnius(tenant)
    if command == "assign_task":
        return client.assign_task(**{k: v for k, v in params.items() if k not in ("tenant", "command")})
    return {"error": f"Unknown omnius command: {command}"}


# ================================================================
# WhatsApp
# ================================================================

def _send_whatsapp(message: str):
    try:
        subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", WA_TARGET, "--message", message],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass


# ================================================================
# Message handler (called by task_monitor when approval keywords detected)
# ================================================================

def handle_approval_message(text: str) -> dict[str, Any] | None:
    """Parse approval/rejection from WhatsApp message."""
    import re

    text_lower = text.lower().strip()

    # "tak #123" / "approve #123"
    match = re.match(r"(?:tak|approve|yes)\s+#?(\d+)", text_lower)
    if match:
        return approve_action(int(match.group(1)))

    # "nie #123" / "reject #123"
    match = re.match(r"(?:nie|reject|no)\s+#?(\d+)", text_lower)
    if match:
        return reject_action(int(match.group(1)))

    # "edit #123: new text"
    match = re.match(r"(?:edit|zmien|zmień)\s+#?(\d+):\s*(.+)", text_lower, re.DOTALL)
    if match:
        return approve_action(int(match.group(1)), edit_text=match.group(2).strip())

    return None


# ================================================================
# Pending actions summary
# ================================================================

def get_pending_actions() -> list[dict[str, Any]]:
    _ensure_table()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, action_type, description, proposed_at
                FROM action_items WHERE status = 'pending'
                ORDER BY proposed_at DESC LIMIT 20
            """)
            return [{"id": r[0], "type": r[1], "description": r[2][:100], "proposed_at": str(r[3])} for r in cur.fetchall()]
