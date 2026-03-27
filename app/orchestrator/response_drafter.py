"""
Smart Response Drafter — auto-responds to incoming communications.

Pipeline (runs every 15 min):
1. Scan recent incoming emails/Teams messages (last 30 min)
2. Classify each: NEEDS_RESPONSE / INFORMATIONAL / ALREADY_RESPONDED
3. For NEEDS_RESPONSE: gather full context (person history, open loops, commitments)
4. Generate draft response using Claude
5. Check standing orders → auto-send or propose for approval
6. Log everything to sent_communications

WhatsApp: monitor responses on Sebastian's behalf via standing orders.
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost
from app.orchestrator.communication import check_scope, send_and_log
from app.orchestrator.action_pipeline import propose_action

load_dotenv()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=120.0)

CLASSIFY_PROMPT = """\
Classify the following incoming message. Return EXACTLY one word:
- NEEDS_RESPONSE — if it contains a question, request, action item, or expects a reply
- INFORMATIONAL — if it is FYI, newsletter, CC-only, automated notification, or no reply expected
- ALREADY_RESPONDED — if it looks like a reply to something already handled

Message from: {sender}
---
{text}
---

Classification:"""

DRAFT_SYSTEM_PROMPT = """\
Jesteś asystentem Sebastiana Jabłońskiego (Prezes REH/REF, trader energetyczny).
Draftujesz odpowiedzi na wiadomości w jego imieniu.

Zasady:
- Pisz po polsku (chyba że oryginalna wiadomość jest po angielsku)
- Bądź profesjonalny, konkretny, bezpośredni
- Nie dodawaj zbędnych grzeczności — Sebastian jest bezpośredni
- Jeśli wiadomość wymaga informacji, których nie masz — zaznacz to
- Podpisuj: "Pozdrawiam, Sebastian" lub "Best regards, Sebastian"
- Uwzględnij kontekst relacji z nadawcą (rola, ostatnie interakcje)
- Jeśli są otwarte tematy z tą osobą, nawiąż do nich
- Odpowiedź zwróć jako JSON: {"to": "...", "subject": "Re: ...", "body": "...", "channel": "email"}"""


# ================================================================
# Table setup
# ================================================================

def _ensure_table():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS response_drafts (
                    id BIGSERIAL PRIMARY KEY,
                    document_id BIGINT REFERENCES documents(id),
                    sender TEXT,
                    channel TEXT,
                    classification TEXT,
                    draft_text TEXT,
                    status TEXT DEFAULT 'drafted',
                    action_item_id BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(document_id)
                )
            """)
        conn.commit()


# ================================================================
# 1. Scan incoming messages
# ================================================================

def scan_incoming_messages(minutes: int = 30) -> list[dict]:
    """Query recent incoming emails and Teams messages from chunks/documents."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, s.source_type, c.text, d.created_at,
                       d.metadata->>'from' as sender, d.metadata->>'to' as recipient
                FROM documents d
                JOIN sources s ON s.id = d.source_id
                JOIN chunks c ON c.document_id = d.id
                WHERE s.source_type IN ('email', 'teams')
                  AND d.created_at > NOW() - INTERVAL '%s minutes'
                  AND d.metadata->>'from' IS NOT NULL
                  AND d.metadata->>'from' NOT LIKE '%%sebastian%%'
                  AND d.metadata->>'from' NOT LIKE '%%jablonski%%'
                ORDER BY d.created_at DESC
            """, (minutes,))
            rows = cur.fetchall()

    # Group chunks by document
    docs: dict[int, dict] = {}
    for doc_id, title, source_type, chunk_text, created_at, sender, recipient in rows:
        if doc_id not in docs:
            docs[doc_id] = {
                "document_id": doc_id,
                "title": title,
                "channel": source_type,
                "sender": sender or "",
                "recipient": recipient or "",
                "created_at": created_at,
                "text": "",
            }
        docs[doc_id]["text"] += chunk_text + "\n"

    # Trim text for each doc
    for doc in docs.values():
        doc["text"] = doc["text"].strip()[:6000]

    return list(docs.values())


# ================================================================
# 2. Classify message
# ================================================================

def classify_message(text: str, sender: str) -> str:
    """Use Haiku to classify: NEEDS_RESPONSE / INFORMATIONAL / ALREADY_RESPONDED."""
    # First check if Sebastian already responded to this sender recently
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM sent_communications
                    WHERE recipient ILIKE %s
                      AND sent_at > NOW() - INTERVAL '24 hours'
                """, (f"%{sender.split('@')[0] if '@' in sender else sender}%",))
                recent_replies = cur.fetchall()[0][0]
        if recent_replies > 0:
            return "ALREADY_RESPONDED"
    except Exception as e:
        log.warning("already_responded_check_failed", error=str(e))

    # LLM classification
    try:
        prompt = CLASSIFY_PROMPT.format(sender=sender, text=text[:2000])
        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=20,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_FAST, "orchestrator.response_drafter.classify", response.usage)

        result = response.content[0].text.strip().upper()

        if "NEEDS_RESPONSE" in result:
            return "NEEDS_RESPONSE"
        elif "ALREADY_RESPONDED" in result:
            return "ALREADY_RESPONDED"
        else:
            return "INFORMATIONAL"
    except Exception as e:
        log.error("classify_message_failed", error=str(e))
        return "INFORMATIONAL"


# ================================================================
# 3. Gather response context
# ================================================================

def gather_response_context(sender: str, message_text: str) -> str:
    """Gather context for drafting a response: person profile, recent events, open loops, thread."""
    context_parts = []

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Person profile
                sender_key = sender.split("@")[0] if "@" in sender else sender
                cur.execute("""
                    SELECT name, role, organization, sentiment_score, notes
                    FROM people
                    WHERE name ILIKE %s OR email ILIKE %s
                    LIMIT 1
                """, (f"%{sender_key}%", f"%{sender_key}%"))
                person = cur.fetchall()
                if person:
                    name, role, org, sentiment, notes = person[0]
                    context_parts.append(
                        f"NADAWCA: {name}, {role or 'brak roli'} @ {org or 'brak org'}, "
                        f"sentiment: {sentiment or 'N/A'}"
                    )
                    if notes:
                        context_parts.append(f"Notatki: {notes[:300]}")

                # Recent events involving sender (last 14 days)
                cur.execute("""
                    SELECT event_type, title, description, event_date
                    FROM events
                    WHERE (description ILIKE %s OR title ILIKE %s)
                      AND created_at > NOW() - INTERVAL '14 days'
                    ORDER BY event_date DESC NULLS LAST
                    LIMIT 5
                """, (f"%{sender_key}%", f"%{sender_key}%"))
                events = cur.fetchall()
                if events:
                    context_parts.append("OSTATNIE WYDARZENIA:")
                    for etype, etitle, edesc, edate in events:
                        context_parts.append(f"- [{etype}] {etitle}: {(edesc or '')[:100]} ({edate})")

                # Open loops / commitments with sender
                cur.execute("""
                    SELECT event_type, title, description
                    FROM events
                    WHERE event_type IN ('commitment', 'decision', 'action_item', 'escalation')
                      AND (description ILIKE %s OR title ILIKE %s)
                      AND created_at > NOW() - INTERVAL '30 days'
                    ORDER BY created_at DESC
                    LIMIT 3
                """, (f"%{sender_key}%", f"%{sender_key}%"))
                loops = cur.fetchall()
                if loops:
                    context_parts.append("OTWARTE TEMATY:")
                    for ltype, ltitle, ldesc in loops:
                        context_parts.append(f"- [{ltype}] {ltitle}: {(ldesc or '')[:150]}")

                # Recent communication thread (same sender, last 7 days)
                cur.execute("""
                    SELECT d.title, LEFT(c.text, 200), d.created_at
                    FROM documents d
                    JOIN sources s ON s.id = d.source_id
                    JOIN chunks c ON c.document_id = d.id
                    WHERE s.source_type IN ('email', 'teams')
                      AND (d.metadata->>'from' ILIKE %s OR d.metadata->>'to' ILIKE %s)
                      AND d.created_at > NOW() - INTERVAL '7 days'
                    ORDER BY d.created_at DESC
                    LIMIT 5
                """, (f"%{sender_key}%", f"%{sender_key}%"))
                thread = cur.fetchall()
                if thread:
                    context_parts.append("OSTATNI WĄTEK:")
                    for ttitle, ttext, tcreated in thread:
                        context_parts.append(f"- {ttitle}: {ttext}... ({tcreated})")

    except Exception as e:
        log.warning("gather_context_failed", error=str(e))
        context_parts.append(f"(Nie udało się zebrać kontekstu: {e})")

    # Keep under 4000 chars
    context = "\n".join(context_parts)
    return context[:4000]


# ================================================================
# 4. Generate response draft
# ================================================================

def generate_response_draft(
    original_message: str, sender: str, channel: str, context: str
) -> dict | None:
    """Use Claude Sonnet to draft a response. Returns dict with to/subject/body/channel."""
    user_prompt = (
        f"Oryginalna wiadomość od: {sender}\n"
        f"Kanał: {channel}\n\n"
        f"--- WIADOMOŚĆ ---\n{original_message[:3000]}\n--- KONIEC ---\n\n"
        f"--- KONTEKST ---\n{context}\n--- KONIEC KONTEKSTU ---\n\n"
        f"Napisz odpowiedź w imieniu Sebastiana. Zwróć JSON."
    )

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=800,
            temperature=0.3,
            system=[{"type": "text", "text": DRAFT_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "orchestrator.response_drafter.draft", response.usage)

        text = response.content[0].text.strip()
        # Extract JSON from markdown code block if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        draft = json.loads(text)
        draft.setdefault("channel", channel)
        draft.setdefault("to", sender)
        return draft
    except Exception as e:
        log.error("response_draft_failed", sender=sender, error=str(e))
        return None


# ================================================================
# 5. Process draft (scope check → send or propose)
# ================================================================

def process_draft(draft: dict) -> dict:
    """Check standing orders via check_scope(). If allowed → send_and_log(). Otherwise → propose_action()."""
    if not draft:
        return {"status": "no_draft"}

    channel = draft.get("channel", "email")
    recipient = draft.get("to", "")
    subject = draft.get("subject", "")
    body = draft.get("body", "")

    # Check standing orders
    scope_check = check_scope(channel, recipient, subject + " " + body)

    if scope_check.get("allowed"):
        result = send_and_log(
            channel=channel,
            recipient=recipient,
            subject=subject,
            body=body,
            authorization_type="standing_order",
            standing_order_id=scope_check.get("order_id"),
        )
        return {"status": "auto_sent", "standing_order": scope_check["order_id"], **result}
    else:
        action_id = propose_action(
            action_type=f"respond_{channel}",
            description=f"Odpowiedź do {recipient}: {subject}",
            draft_params={"to": recipient, "subject": subject, "body": body, "channel": channel},
            source="response_drafter",
        )
        return {"status": "proposed", "action_id": action_id, "reason": scope_check.get("reason")}


# ================================================================
# 6. Main pipeline
# ================================================================

def run_response_drafter(minutes: int = 30) -> dict:
    """Main pipeline: scan, classify, draft, process."""
    _ensure_table()

    summary = {
        "scanned": 0,
        "needs_response": 0,
        "drafted": 0,
        "auto_sent": 0,
        "proposed": 0,
        "errors": 0,
    }

    # 1. Scan incoming messages
    messages = scan_incoming_messages(minutes=minutes)
    summary["scanned"] = len(messages)
    log.info("response_drafter_scan", count=len(messages), minutes=minutes)

    for msg in messages:
        doc_id = msg["document_id"]

        # Skip already processed documents
        try:
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM response_drafts WHERE document_id = %s",
                        (doc_id,),
                    )
                    if cur.fetchall():
                        log.debug("response_drafter_skip_processed", document_id=doc_id)
                        continue
        except Exception:
            pass

        # 2. Classify
        classification = classify_message(msg["text"], msg["sender"])
        log.info(
            "response_drafter_classified",
            document_id=doc_id,
            sender=msg["sender"],
            classification=classification,
        )

        if classification != "NEEDS_RESPONSE":
            # Log classification to avoid re-processing
            try:
                with get_pg_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO response_drafts (document_id, sender, channel, classification, status)
                            VALUES (%s, %s, %s, %s, 'skipped')
                            ON CONFLICT (document_id) DO NOTHING
                        """, (doc_id, msg["sender"], msg["channel"], classification))
                    conn.commit()
            except Exception as e:
                log.warning("response_draft_log_failed", error=str(e))
            continue

        summary["needs_response"] += 1

        # 3. Gather context + generate draft
        try:
            context = gather_response_context(msg["sender"], msg["text"])
            draft = generate_response_draft(
                original_message=msg["text"],
                sender=msg["sender"],
                channel=msg["channel"],
                context=context,
            )

            if not draft:
                summary["errors"] += 1
                continue

            summary["drafted"] += 1

            # 4. Process (scope check → send or propose)
            result = process_draft(draft)

            if result.get("status") == "auto_sent":
                summary["auto_sent"] += 1
            elif result.get("status") == "proposed":
                summary["proposed"] += 1

            # Log to response_drafts
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO response_drafts
                            (document_id, sender, channel, classification, draft_text, status, action_item_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (document_id) DO NOTHING
                    """, (
                        doc_id,
                        msg["sender"],
                        msg["channel"],
                        classification,
                        json.dumps(draft, ensure_ascii=False, default=str),
                        result.get("status", "drafted"),
                        result.get("action_id"),
                    ))
                conn.commit()

            log.info(
                "response_drafter_processed",
                document_id=doc_id,
                sender=msg["sender"],
                status=result.get("status"),
            )

        except Exception as e:
            summary["errors"] += 1
            log.error("response_drafter_error", document_id=doc_id, error=str(e))

    log.info("response_drafter_complete", **summary)
    return summary


# ================================================================
# CLI
# ================================================================

if __name__ == "__main__":
    import sys

    minutes = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    result = run_response_drafter(minutes=minutes)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
