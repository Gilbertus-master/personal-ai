"""
Response Tracking Engine — tracks whether communications got responses.

After sending email/Teams/WhatsApp on Sebastian's behalf:
1. Scan for response from recipient within 24h/72h
2. Measure response time
3. Detect response sentiment
4. Auto-send follow-up reminder if no response after 72h (if authority allows)
5. Feed data into channel effectiveness and standing order metrics

Cron: every 4h (aligned with action outcome tracker)
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional, TypedDict

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

log = structlog.get_logger(__name__)

ANTHROPIC_FAST = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)


def _to_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


# ================================================================
# Database
# ================================================================

_tables_ensured = False
_ensure_tables_lock = threading.Lock()

def _ensure_tables():
    """Add response tracking columns to sent_communications."""
    global _tables_ensured
    with _ensure_tables_lock:
        if _tables_ensured:
            return
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE sent_communications
                        ADD COLUMN IF NOT EXISTS response_received BOOLEAN DEFAULT FALSE
                """)
                cur.execute("""
                    ALTER TABLE sent_communications
                        ADD COLUMN IF NOT EXISTS response_time_hours NUMERIC
                """)
                cur.execute("""
                    ALTER TABLE sent_communications
                        ADD COLUMN IF NOT EXISTS response_sentiment TEXT
                """)
                cur.execute("""
                    ALTER TABLE sent_communications
                        ADD COLUMN IF NOT EXISTS response_chunk_id BIGINT
                """)
                cur.execute("""
                    ALTER TABLE sent_communications
                        ADD COLUMN IF NOT EXISTS follow_up_sent BOOLEAN DEFAULT FALSE
                """)
                cur.execute("""
                    ALTER TABLE sent_communications
                        ADD COLUMN IF NOT EXISTS follow_up_count INT DEFAULT 0
                """)
                cur.execute("""
                    ALTER TABLE sent_communications
                        ADD COLUMN IF NOT EXISTS checked_at TIMESTAMPTZ
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sent_comms_response
                        ON sent_communications(response_received)
                        WHERE response_received = FALSE
                """)
            conn.commit()
        log.debug("response_tracker_tables_ensured")
        _tables_ensured = True


# ================================================================
# 1. Find unchecked communications
# ================================================================

def get_unchecked_communications(
    hours_ago_min: int = 24,
    hours_ago_max: int = 168,
) -> list[dict]:
    """Find sent_communications awaiting response check.

    Returns comms where:
    - sent between hours_ago_max and hours_ago_min ago
    - response_received = FALSE
    - checked_at is NULL or older than 12 hours
    """
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sc.id, sc.channel, sc.recipient, sc.subject, sc.body,
                       sc.sent_at, sc.standing_order_id, sc.checked_at,
                       sc.follow_up_sent, sc.follow_up_count
                FROM sent_communications sc
                WHERE sc.response_received = FALSE
                  AND sc.sent_at > NOW() - (%s * INTERVAL '1 hour')
                  AND sc.sent_at < NOW() - (%s * INTERVAL '1 hour')
                  AND (sc.checked_at IS NULL
                       OR sc.checked_at < NOW() - INTERVAL '12 hours')
                ORDER BY sc.sent_at ASC
                LIMIT 30
            """, (hours_ago_max, hours_ago_min))
            rows = cur.fetchall()

    comms = []
    for r in rows:
        comms.append({
            "id": r[0],
            "channel": r[1],
            "recipient": r[2],
            "subject": r[3],
            "body": r[4],
            "sent_at": r[5],
            "standing_order_id": r[6],
            "checked_at": r[7],
            "follow_up_sent": r[8],
            "follow_up_count": r[9],
        })
    return comms


# ================================================================
# 2. Scan for response
# ================================================================

def scan_for_response(comm: dict) -> dict:
    """Search incoming messages from the recipient after sent_at.

    For email: search chunks from source_type='email' mentioning recipient/subject.
    For teams: search chunks from source_type='teams' mentioning recipient.
    For whatsapp: search chunks from source_type='whatsapp'.
    """
    sent_at = comm["sent_at"]
    now = datetime.now(timezone.utc)
    recipient = comm.get("recipient", "")
    subject = comm.get("subject", "") or ""

    # Build search patterns
    if "@" in recipient:
        recipient_name = recipient.split("@")[0].replace(".", " ")
    else:
        recipient_name = recipient
    recipient_pattern = f"%{recipient_name.lower()}%"
    subject_pattern = f"%{subject[:50].lower()}%" if subject else "%"

    # Determine source_types to search
    channel = comm.get("channel", "email")
    if channel == "email":
        source_types = ("email",)
    elif channel == "teams":
        source_types = ("teams",)
    elif channel == "whatsapp":
        source_types = ("whatsapp",)
    else:
        source_types = ("email", "teams")

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, LEFT(c.text, 500), d.created_at, d.title
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE s.source_type = ANY(%s)
                  AND d.created_at > %s
                  AND d.created_at < %s
                  AND (
                      LOWER(d.title) LIKE %s
                      OR LOWER(c.text) LIKE %s
                  )
                ORDER BY d.created_at ASC
                LIMIT 5
            """, (list(source_types), sent_at, now, recipient_pattern, subject_pattern))
            matches = cur.fetchall()

    if matches:
        earliest = min(r[2] for r in matches if r[2])
        response_hours = None
        if earliest and sent_at:
            sent_at_aware = _to_utc(sent_at)
            earliest_aware = _to_utc(earliest)
            delta = earliest_aware - sent_at_aware
            response_hours = round(delta.total_seconds() / 3600, 1)

        # Analyze sentiment of earliest response
        response_text = matches[0][1] or ""
        sentiment = analyze_response_sentiment(response_text) if response_text else "neutral"

        return {
            "found": True,
            "response_received": True,
            "response_time_hours": response_hours,
            "response_sentiment": sentiment,
            "response_chunk_id": matches[0][0],
            "match_count": len(matches),
        }

    # No response found
    elapsed_hours = (now - _to_utc(sent_at)).total_seconds() / 3600
    needs_follow_up = (
        elapsed_hours > 72
        and not comm.get("follow_up_sent", False)
    )

    return {
        "found": False,
        "response_received": False,
        "response_time_hours": None,
        "response_sentiment": None,
        "response_chunk_id": None,
        "needs_follow_up": needs_follow_up,
        "elapsed_hours": round(elapsed_hours, 1),
    }


# ================================================================
# 3. Sentiment analysis
# ================================================================

def analyze_response_sentiment(response_text: str) -> str:
    """Use Haiku to classify response tone: positive, neutral, or negative."""
    if not response_text or len(response_text.strip()) < 10:
        return "neutral"

    try:
        response = client.messages.create(
            model=ANTHROPIC_FAST,
            max_tokens=10,
            temperature=0.0,
            system=[{
                "type": "text",
                "text": "Classify the tone of this response: positive, neutral, or negative. Return just the single word.",
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": response_text[:1000]}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_FAST, "analysis.response_tracker.sentiment", response.usage)

        result = response.content[0].text.strip().lower()
        if result in ("positive", "neutral", "negative"):
            return result
        return "neutral"

    except Exception as e:
        log.error("sentiment_analysis_error", error=str(e))
        return "neutral"


# ================================================================
# 4. Send follow-up
# ================================================================

class CommDict(TypedDict, total=False):
    """Shape of the comm record passed to send_follow_up."""
    channel: str               # required — delivery channel, e.g. "email", "teams", "whatsapp"
    recipient: str             # required — address / handle of the recipient
    subject: Optional[str]     # optional — message subject line
    follow_up_sent: bool       # optional — whether a follow-up was already sent
    follow_up_count: int       # optional — number of follow-ups sent so far
    standing_order_id: Optional[int]  # optional — linked standing order, if any


def send_follow_up(comm_id: int, comm: CommDict) -> dict:
    """Send follow-up reminder if authority allows (send_reminder = level 1)."""
    from app.orchestrator.authority import check_authority

    auth = check_authority("send_reminder")
    if not auth.get("authorized", False):
        log.info("follow_up_not_authorized", comm_id=comm_id, level=auth.get("level"))
        # Propose via action pipeline instead
        try:
            from app.orchestrator.action_pipeline import propose_action
            propose_action(
                action_type="send_reminder",
                description=f"Follow-up: brak odpowiedzi od {comm['recipient']} "
                            f"na wiadomość '{comm.get('subject', '(brak tematu)')}'",
                params={
                    "channel": comm["channel"],
                    "recipient": comm["recipient"],
                    "original_comm_id": comm_id,
                    "subject": f"Re: {comm.get('subject', '')}",
                },
            )
        except Exception as e:
            log.error("follow_up_proposal_error", comm_id=comm_id, error=str(e))
        return {"status": "proposed", "comm_id": comm_id}

    # Auto-execute follow-up
    try:
        from app.orchestrator.communication import send_and_log
        subject = f"Re: {comm.get('subject', '')}" if comm.get("subject") else None
        body = (
            "Dzień dobry,\n\n"
            "Chciałem się upewnić, że moja wcześniejsza wiadomość dotarła. "
            "Będę wdzięczny za informację zwrotną.\n\n"
            "Pozdrawiam,\nSebastian Jabłoński"
        )
        result = send_and_log(
            channel=comm["channel"],
            recipient=comm["recipient"],
            subject=subject,
            body=body,
            authorization_type="auto_follow_up",
            standing_order_id=comm.get("standing_order_id"),
        )

        # Update follow-up tracking
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE sent_communications
                    SET follow_up_sent = TRUE,
                        follow_up_count = COALESCE(follow_up_count, 0) + 1
                    WHERE id = %s
                """, (comm_id,))
            conn.commit()

        log.info("follow_up_sent", comm_id=comm_id, channel=comm["channel"],
                 recipient=comm["recipient"])
        return {"status": "sent", "comm_id": comm_id, **result}

    except Exception as e:
        log.error("follow_up_send_error", comm_id=comm_id, error=str(e))
        return {"status": "error", "comm_id": comm_id, "error": str(e)}


# ================================================================
# 5. Response stats
# ================================================================

def get_response_stats(days: int = 30) -> dict:
    """Aggregate response statistics by channel and person."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Total sent
            cur.execute("""
                SELECT COUNT(*) FROM sent_communications
                WHERE sent_at > NOW() - (%s * INTERVAL '1 day')
            """, (days,))
            rows = cur.fetchall()
            total_sent = rows[0][0] if rows else 0

            # Total responded
            cur.execute("""
                SELECT COUNT(*) FROM sent_communications
                WHERE sent_at > NOW() - (%s * INTERVAL '1 day')
                  AND response_received = TRUE
            """, (days,))
            rows = cur.fetchall()
            responded = rows[0][0] if rows else 0

            # Average response time
            cur.execute("""
                SELECT AVG(response_time_hours)
                FROM sent_communications
                WHERE sent_at > NOW() - (%s * INTERVAL '1 day')
                  AND response_time_hours IS NOT NULL
            """, (days,))
            rows = cur.fetchall()
            avg_row = rows[0] if rows else None
            avg_hours = round(float(avg_row[0]), 1) if avg_row and avg_row[0] else None

            # By channel
            cur.execute("""
                SELECT channel,
                       COUNT(*) as sent,
                       COUNT(*) FILTER (WHERE response_received = TRUE) as responded,
                       AVG(response_time_hours) FILTER (WHERE response_time_hours IS NOT NULL) as avg_hours
                FROM sent_communications
                WHERE sent_at > NOW() - (%s * INTERVAL '1 day')
                GROUP BY channel
                ORDER BY sent DESC
            """, (days,))
            by_channel = {}
            for r in cur.fetchall():
                ch_sent = r[1]
                ch_responded = r[2]
                by_channel[r[0]] = {
                    "sent": ch_sent,
                    "responded": ch_responded,
                    "rate": round(ch_responded / ch_sent, 3) if ch_sent > 0 else 0.0,
                    "avg_hours": round(float(r[3]), 1) if r[3] else None,
                }

            # By person
            cur.execute("""
                SELECT recipient,
                       COUNT(*) as sent,
                       COUNT(*) FILTER (WHERE response_received = TRUE) as responded,
                       AVG(response_time_hours) FILTER (WHERE response_time_hours IS NOT NULL) as avg_hours,
                       MODE() WITHIN GROUP (ORDER BY response_sentiment) FILTER (WHERE response_sentiment IS NOT NULL) as common_sentiment
                FROM sent_communications
                WHERE sent_at > NOW() - (%s * INTERVAL '1 day')
                GROUP BY recipient
                HAVING COUNT(*) >= 2
                ORDER BY sent DESC
            """, (days,))
            by_person = {}
            for r in cur.fetchall():
                p_sent = r[1]
                p_responded = r[2]
                by_person[r[0]] = {
                    "sent": p_sent,
                    "responded": p_responded,
                    "rate": round(p_responded / p_sent, 3) if p_sent > 0 else 0.0,
                    "avg_hours": round(float(r[3]), 1) if r[3] else None,
                    "sentiment_avg": r[4] or "unknown",
                }

            # No-response streaks: people with consecutive non-responses
            cur.execute("""
                WITH recent AS (
                    SELECT recipient, channel, response_received, sent_at,
                           ROW_NUMBER() OVER (PARTITION BY recipient ORDER BY sent_at DESC) as rn
                    FROM sent_communications
                    WHERE sent_at > NOW() - (%s * INTERVAL '1 day')
                ),
                streaks AS (
                    SELECT recipient,
                           COUNT(*) as consecutive,
                           ARRAY_AGG(DISTINCT channel) as channels
                    FROM recent
                    WHERE response_received = FALSE
                      AND rn <= (
                          SELECT COALESCE(MIN(rn2.rn) - 1, COUNT(*))
                          FROM recent rn2
                          WHERE rn2.recipient = recent.recipient
                            AND rn2.response_received = TRUE
                      )
                    GROUP BY recipient
                    HAVING COUNT(*) >= 2
                )
                SELECT recipient, consecutive, channels
                FROM streaks
                ORDER BY consecutive DESC
            """, (days,))
            no_response_streak = []
            for r in cur.fetchall():
                no_response_streak.append({
                    "person": r[0],
                    "consecutive_no_response": r[1],
                    "channels_tried": r[2],
                })

    response_rate = round(responded / total_sent, 3) if total_sent > 0 else 0.0

    return {
        "total_sent": total_sent,
        "responded": responded,
        "response_rate": response_rate,
        "avg_response_time_hours": avg_hours,
        "by_channel": by_channel,
        "by_person": by_person,
        "no_response_streak": no_response_streak,
    }


# ================================================================
# 6. Main pipeline
# ================================================================

def run_response_tracking() -> dict:
    """Main pipeline: check unchecked comms, scan for responses, send follow-ups."""
    log.info("response_tracking_start")
    _ensure_tables()

    comms = get_unchecked_communications()
    log.info("unchecked_communications", count=len(comms))

    checked = 0
    responses_found = 0
    follow_ups_sent = 0

    for comm in comms:
        comm_id = comm["id"]

        try:
            result = scan_for_response(comm)

            if result.get("response_received"):
                # Update with response data
                with get_pg_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE sent_communications
                            SET response_received = TRUE,
                                response_time_hours = %s,
                                response_sentiment = %s,
                                response_chunk_id = %s,
                                checked_at = NOW()
                            WHERE id = %s
                        """, (
                            result["response_time_hours"],
                            result["response_sentiment"],
                            result["response_chunk_id"],
                            comm_id,
                        ))
                    conn.commit()
                responses_found += 1
                log.info("response_found",
                         comm_id=comm_id,
                         hours=result["response_time_hours"],
                         sentiment=result["response_sentiment"])
            else:
                # Mark as checked (no response yet)
                with get_pg_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE sent_communications
                            SET checked_at = NOW()
                            WHERE id = %s
                        """, (comm_id,))
                    conn.commit()

                # Send follow-up if needed
                if result.get("needs_follow_up"):
                    fu_result = send_follow_up(comm_id, comm)
                    if fu_result.get("status") == "sent":
                        follow_ups_sent += 1

            checked += 1

        except Exception as e:
            log.error("response_check_error", comm_id=comm_id, error=str(e))

    summary = {
        "status": "ok",
        "checked": checked,
        "responses_found": responses_found,
        "follow_ups_sent": follow_ups_sent,
    }

    log.info("response_tracking_complete", **summary)
    return summary


# ================================================================
# CLI
# ================================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        result = get_response_stats(days)
    else:
        result = run_response_tracking()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
