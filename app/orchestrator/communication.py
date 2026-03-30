"""
Communication on behalf of Sebastian.

Two authorization modes:
1. Per message: Gilbertus drafts → Sebastian approves on WhatsApp → send
2. Standing orders: Sebastian pre-authorizes scope → Gilbertus sends within scope → daily digest

WhatsApp commands:
  authorize: email roch@* statusy projektów, max 3/dzień, nigdy wynagrodzenia
  revoke #ID
  list orders
  digest
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import os
import re
import subprocess
from typing import Any

from app.db.postgres import get_pg_connection

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "+48505441635")


# ================================================================
# Standing Orders CRUD
# ================================================================

def create_standing_order(text: str) -> dict[str, Any]:
    """Parse 'authorize:' command and create standing order.

    Format: authorize: [channel] [recipient] [topic_scope], max N/dzień, nigdy [forbidden]
    Example: authorize: email roch@* statusy projektów i follow-upy, max 3/dzień, nigdy wynagrodzenia/zwolnienia
    """
    # Parse channel
    channel = "email"  # default
    for ch in ["email", "teams", "whatsapp"]:
        if ch in text.lower():
            channel = ch
            break

    # Parse recipient pattern
    recipient = "*"
    email_match = re.search(r'([\w.]+@[\w.*]+)', text)
    if email_match:
        recipient = email_match.group(1)
    elif "roch" in text.lower():
        recipient = "*baranowski*"
    elif "krystian" in text.lower():
        recipient = "*juchacz*"

    # Parse max per day
    max_per_day = 3
    max_match = re.search(r'max\s+(\d+)', text)
    if max_match:
        max_per_day = int(max_match.group(1))

    # Parse forbidden topics
    forbidden = None
    nigdy_match = re.search(r'nigdy\s+(.+?)(?:\.|$)', text, re.IGNORECASE)
    if nigdy_match:
        forbidden = nigdy_match.group(1).strip()

    # Topic scope = everything between channel/recipient and "max"/"nigdy"
    topic_scope = text
    # Clean up
    for remove in ["authorize:", channel, recipient, f"max {max_per_day}", f"nigdy {forbidden or ''}"]:
        topic_scope = topic_scope.replace(remove, "")
    topic_scope = re.sub(r'\s+', ' ', topic_scope).strip(" ,./")
    if not topic_scope:
        topic_scope = "ogólna komunikacja"

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO standing_orders (channel, recipient_pattern, topic_scope, forbidden_topics, max_per_day)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (channel, recipient, topic_scope, forbidden, max_per_day))
            order_id = cur.fetchall()[0][0]
        conn.commit()

    return {
        "order_id": order_id,
        "channel": channel,
        "recipient": recipient,
        "topic_scope": topic_scope,
        "forbidden": forbidden,
        "max_per_day": max_per_day,
    }


def revoke_standing_order(order_id: int) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE standing_orders SET active = FALSE WHERE id = %s AND active = TRUE", (order_id,))
            if cur.rowcount == 0:
                return {"error": f"Standing order #{order_id} not found or already revoked"}
        conn.commit()
    return {"order_id": order_id, "status": "revoked"}


def list_standing_orders() -> list[dict[str, Any]]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, channel, recipient_pattern, topic_scope, forbidden_topics, max_per_day, created_at
                FROM standing_orders WHERE active = TRUE ORDER BY id
            """)
            return [
                {"id": r[0], "channel": r[1], "recipient": r[2], "scope": r[3],
                 "forbidden": r[4], "max_per_day": r[5], "created": str(r[6])}
                for r in cur.fetchall()
            ]


# ================================================================
# Scope Checker (B1.8)
# ================================================================

def check_scope(channel: str, recipient: str, topic: str) -> dict[str, Any]:
    """Check if a message fits within any active standing order."""
    orders = list_standing_orders()

    for order in orders:
        if order["channel"] != channel:
            continue

        # Check recipient pattern (wildcard matching)
        pattern = "^" + re.escape(order["recipient"]).replace(r"\*", ".*") + "$"
        if not re.match(pattern, recipient, re.IGNORECASE):
            continue

        # Check forbidden topics
        if order["forbidden"]:
            for forbidden in order["forbidden"].split("/"):
                if forbidden.strip().lower() in topic.lower():
                    return {"allowed": False, "reason": f"Forbidden topic: {forbidden.strip()}", "order_id": order["id"]}

        # Check daily limit
        today_count = _count_today_sends(order["id"])
        if today_count >= order["max_per_day"]:
            return {"allowed": False, "reason": f"Daily limit reached ({today_count}/{order['max_per_day']})", "order_id": order["id"]}

        # Topic scope match — bidirectional keyword containment
        scope_keywords = [w.strip().lower() for w in re.split(r'[,\s/]+', order["scope"]) if len(w.strip()) > 2]
        topic_lower = topic.lower()
        topic_words = [w.strip().lower() for w in re.split(r'[,\s/]+', topic) if len(w.strip()) > 2]
        # Match if any scope keyword is in topic OR any topic word is in scope
        scope_text = order["scope"].lower()
        match = any(kw in topic_lower for kw in scope_keywords) or any(tw in scope_text for tw in topic_words)
        if match or not scope_keywords:
            return {"allowed": True, "order_id": order["id"], "remaining_today": order["max_per_day"] - today_count}

    return {"allowed": False, "reason": "No matching standing order", "order_id": None}


def _count_today_sends(order_id: int) -> int:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM sent_communications
                WHERE standing_order_id = %s AND sent_at > CURRENT_DATE
            """, (order_id,))
            return cur.fetchall()[0][0]


# ================================================================
# Send + Log
# ================================================================

def send_and_log(
    channel: str,
    recipient: str,
    subject: str | None,
    body: str,
    authorization_type: str,
    standing_order_id: int | None = None,
    action_item_id: int | None = None,
) -> dict[str, Any]:
    """Send message and log to sent_communications."""

    # Execute send
    if channel == "email":
        result = _send_email(recipient, subject or "(no subject)", body)
    elif channel == "teams":
        result = _send_teams(recipient, body)
    elif channel == "whatsapp":
        result = _send_whatsapp_to(recipient, body)
    else:
        return {"error": f"Unknown channel: {channel}"}

    # Log
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sent_communications (channel, recipient, subject, body, standing_order_id, action_item_id, authorization_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (channel, recipient, subject, body, standing_order_id, action_item_id, authorization_type))
            comm_id = cur.fetchall()[0][0]
        conn.commit()

    return {"comm_id": comm_id, "channel": channel, "recipient": recipient, "status": "sent", **result}


def _send_email(to: str, subject: str, body: str) -> dict:
    try:
        from app.ingestion.graph_api.auth import get_access_token
        import requests
        token = get_access_token()
        user_id = os.getenv("MS_GRAPH_USER_ID")
        resp = requests.post(
            f"https://graph.microsoft.com/v1.0/users/{user_id}/sendMail",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            }},
            timeout=30,
        )
        resp.raise_for_status()
        return {"email_status": "sent"}
    except Exception as e:
        return {"email_status": "error", "error": str(e)}


def _send_teams(recipient: str, message: str) -> dict:
    """Send Teams message via Graph API."""
    try:
        from app.ingestion.graph_api.auth import get_access_token
        import requests

        token = get_access_token()
        user_id = os.getenv("MS_GRAPH_USER_ID")

        # Find or create 1:1 chat with recipient
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Search for user
        search_resp = requests.get(
            f"https://graph.microsoft.com/v1.0/users?$filter=mail eq '{recipient}' or userPrincipalName eq '{recipient}'",
            headers=headers, timeout=15,
        )
        users = search_resp.json().get("value", [])
        if not users:
            return {"teams_status": "user_not_found", "recipient": recipient}

        target_id = users[0]["id"]

        # Create or get chat
        chat_resp = requests.post(
            "https://graph.microsoft.com/v1.0/chats",
            headers=headers,
            json={
                "chatType": "oneOnOne",
                "members": [
                    {"@odata.type": "#microsoft.graph.aadUserConversationMember",
                     "roles": ["owner"], "user@odata.bind": f"https://graph.microsoft.com/v1.0/users/{user_id}"},
                    {"@odata.type": "#microsoft.graph.aadUserConversationMember",
                     "roles": ["owner"], "user@odata.bind": f"https://graph.microsoft.com/v1.0/users/{target_id}"},
                ],
            },
            timeout=15,
        )
        chat_id = chat_resp.json().get("id")
        if not chat_id:
            return {"teams_status": "chat_creation_failed"}

        # Send message
        msg_resp = requests.post(
            f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages",
            headers=headers,
            json={"body": {"content": message}},
            timeout=15,
        )
        msg_resp.raise_for_status()
        return {"teams_status": "sent", "chat_id": chat_id}
    except Exception as e:
        return {"teams_status": "error", "error": str(e)}


def _send_whatsapp_to(recipient: str, message: str) -> dict:
    try:
        result = subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", recipient, "--message", message],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log.error("whatsapp_send_failed", recipient=recipient,
                      returncode=result.returncode, stderr=result.stderr[:200])
            return {"whatsapp_status": "error", "error": f"returncode={result.returncode}"}
        return {"whatsapp_status": "sent"}
    except Exception as e:
        log.error("whatsapp_send_exception", recipient=recipient, error=str(e))
        return {"whatsapp_status": "error", "error": str(e)}


# ================================================================
# Daily Digest (B1.6)
# ================================================================

def generate_daily_digest() -> str:
    """Generate digest of all communications sent today on behalf of Sebastian."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Today's sends
            cur.execute("""
                SELECT channel, recipient, subject, authorization_type
                FROM sent_communications
                WHERE sent_at > CURRENT_DATE
                ORDER BY sent_at
            """)
            sends = cur.fetchall()

            # Active standing orders
            cur.execute("SELECT COUNT(*) FROM standing_orders WHERE active = TRUE")
            active_orders = cur.fetchall()[0][0]

            # Pending actions
            cur.execute("SELECT COUNT(*) FROM action_items WHERE status = 'pending'")
            pending = cur.fetchall()[0][0]

    if not sends:
        lines = ["\U0001f4ca Dzi\u015b w Twoim imieniu: nic nie wys\u0142a\u0142em."]
    else:
        by_channel = {}
        for ch, recip, subj, auth in sends:
            if ch not in by_channel:
                by_channel[ch] = []
            by_channel[ch].append(f"{recip}" + (f" ({subj})" if subj else ""))

        lines = ["\U0001f4ca Dzi\u015b w Twoim imieniu:"]
        for ch, items in by_channel.items():
            lines.append(f"- {len(items)} {ch}: {', '.join(items[:3])}")

    lines.append(f"\nStanding orders: {active_orders} aktywne")
    lines.append(f"Pending approval: {pending}")

    return "\n".join(lines)


# ================================================================
# WhatsApp command handler
# ================================================================

def handle_communication_command(text: str) -> dict[str, Any] | None:
    """Handle authorize/revoke/list/digest commands from WhatsApp."""
    text_lower = text.lower().strip()

    if text_lower.startswith("authorize:"):
        result = create_standing_order(text)
        return {
            "type": "standing_order_created",
            "response": f"\u2705 Standing order #{result['order_id']} utworzony:\n"
                        f"Kana\u0142: {result['channel']}\n"
                        f"Odbiorca: {result['recipient']}\n"
                        f"Zakres: {result['topic_scope']}\n"
                        f"Zakazane: {result['forbidden'] or 'brak'}\n"
                        f"Max/dzie\u0144: {result['max_per_day']}",
        }

    if text_lower.startswith("revoke") and "#" in text_lower:
        match = re.search(r'#(\d+)', text_lower)
        if match:
            result = revoke_standing_order(int(match.group(1)))
            return {"type": "revoked", "response": f"\u274c Standing order #{match.group(1)} anulowany."}

    if text_lower in ("list orders", "lista zlecen", "standing orders"):
        orders = list_standing_orders()
        if not orders:
            return {"type": "list", "response": "Brak aktywnych standing orders."}
        lines = ["\U0001f4cb Aktywne standing orders:"]
        for o in orders:
            lines.append(f"#{o['id']} [{o['channel']}] {o['recipient']}: {o['scope']} (max {o['max_per_day']}/dz)")
        return {"type": "list", "response": "\n".join(lines)}

    if text_lower in ("digest", "raport", "co wyslales"):
        return {"type": "digest", "response": generate_daily_digest()}

    return None
