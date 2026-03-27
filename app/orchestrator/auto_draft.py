"""
Auto-draft engine — detects communication needs from new data and drafts messages.

Triggers:
- New opportunity detected → draft follow-up email
- Alert fired (stale decision, missing communication) → draft reminder
- Calendar meeting tomorrow → draft prep email to attendees
- Escalation/blocker event → draft intervention

For each draft: checks standing orders. If within scope → send directly.
Otherwise → propose via action pipeline for approval.

Runs as part of opportunity detector (co 2h) or standalone.
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost
from app.orchestrator.communication import check_scope, send_and_log
from app.orchestrator.action_pipeline import propose_action

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

DRAFT_PROMPT = """You draft professional business emails in Polish on behalf of Sebastian Jabłoński,
board member of Respect Energy Holding and Respect Energy Fuels.

Given context about what needs to be communicated, draft a concise email:
- Subject line (short, clear)
- Body (professional, direct, action-oriented)
- Suggested recipient email

Return JSON:
{"to": "email@example.com", "subject": "...", "body": "...", "channel": "email"}

Write in Polish. Be direct. No fluff. Sign as "Sebastian Jabłoński" or "Pozdrawiam, Sebastian"."""


def draft_from_opportunity(opportunity_id: int) -> dict[str, Any] | None:
    """Draft communication based on a detected opportunity."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT opportunity_type, description, estimated_value_pln
                FROM opportunities WHERE id = %s
            """, (opportunity_id,))
            rows = cur.fetchall()
            if not rows:
                return None
            otype, desc, value = rows[0]

    context = f"Opportunity type: {otype}\nDescription: {desc}\nEstimated value: {value} PLN/year\n\nDraft an appropriate email to address this."

    return _generate_draft(context, source=f"opportunity #{opportunity_id}")


def draft_from_alert(alert_type: str, title: str, description: str) -> dict[str, Any] | None:
    """Draft communication based on an alert."""
    context = f"Alert: {alert_type}\nTitle: {title}\nDetails: {description}\n\nDraft a follow-up email to address this alert."
    return _generate_draft(context, source=f"alert: {title[:50]}")


def draft_meeting_prep(meeting_subject: str, attendees: list[str], context_notes: str = "") -> dict[str, Any] | None:
    """Draft prep email before a meeting."""
    context = f"Tomorrow's meeting: {meeting_subject}\nAttendees: {', '.join(attendees)}\nContext: {context_notes}\n\nDraft a short prep email to key attendees with agenda/questions."
    return _generate_draft(context, source=f"meeting prep: {meeting_subject[:50]}")


def _generate_draft(context: str, source: str = "auto") -> dict[str, Any] | None:
    """Generate email draft via LLM."""
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=500,
            temperature=0.2,
            system=[{"type": "text", "text": DRAFT_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "orchestrator.auto_draft", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        draft = json.loads(text)
        draft["source"] = source
        return draft
    except Exception as e:
        log.error("draft_generation_failed", error=str(e))
        return None


def process_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Check scope and either send directly or propose for approval."""
    if not draft:
        return {"status": "no_draft"}

    channel = draft.get("channel", "email")
    recipient = draft.get("to", "")
    subject = draft.get("subject", "")
    body = draft.get("body", "")

    # Check standing orders
    scope_check = check_scope(channel, recipient, subject + " " + body)

    if scope_check.get("allowed"):
        # Send directly under standing order
        result = send_and_log(
            channel=channel,
            recipient=recipient,
            subject=subject,
            body=body,
            authorization_type="standing_order",
            standing_order_id=scope_check.get("order_id"),
        )
        return {"status": "sent_directly", "standing_order": scope_check["order_id"], **result}
    else:
        # Propose for approval
        action_id = propose_action(
            action_type=f"send_{channel}",
            description=f"Email do {recipient}: {subject}",
            draft_params={"to": recipient, "subject": subject, "body": body, "channel": channel},
            source=draft.get("source", "auto_draft"),
        )
        return {"status": "proposed", "action_id": action_id, "reason": scope_check.get("reason")}


def run_auto_drafts() -> list[dict[str, Any]]:
    """Run all auto-draft triggers."""
    results = []

    # 1. Draft for new opportunities
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM opportunities
                WHERE status = 'new' AND created_at > NOW() - INTERVAL '4 hours'
                  AND action_item_id IS NULL
                ORDER BY roi_score DESC NULLS LAST LIMIT 3
            """)
            opp_ids = [r[0] for r in cur.fetchall()]

    for oid in opp_ids:
        draft = draft_from_opportunity(oid)
        if draft:
            result = process_draft(draft)
            result["trigger"] = f"opportunity #{oid}"
            # Link action_item back to opportunity to prevent re-drafting
            if result.get("action_id"):
                with get_pg_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE opportunities SET action_item_id = %s WHERE id = %s",
                            (result["action_id"], oid),
                        )
                    conn.commit()
            results.append(result)

    # 2. Draft for stale alerts (decisions without follow-up)
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT alert_type, title, description FROM alerts
                WHERE is_active = TRUE AND created_at > NOW() - INTERVAL '24 hours'
                  AND alert_type = 'decision_no_followup'
                LIMIT 2
            """)
            alerts = cur.fetchall()

    for atype, title, desc in alerts:
        draft = draft_from_alert(atype, title, desc)
        if draft:
            result = process_draft(draft)
            result["trigger"] = f"alert: {title[:40]}"
            results.append(result)

    return results


if __name__ == "__main__":
    results = run_auto_drafts()
    for r in results:
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
