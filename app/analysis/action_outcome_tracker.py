"""
Action Outcome Tracker — closes the feedback loop on executed actions.

After Gilbertus executes an action (send_email, create_ticket, schedule_meeting,
send_whatsapp), this module checks the outcome:
- 24h: Did the recipient respond?
- 72h: Did the topic appear in new events?
- 7d: Did the related open loop close?

Outcomes feed back into:
- Standing order effectiveness
- Person responsiveness profile
- Rule reinforcement
- Decision learning

Cron: every 6h
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone

import structlog
from anthropic import Anthropic
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection
from app.db.cost_tracker import log_anthropic_cost

load_dotenv()

log = structlog.get_logger(__name__)

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"), timeout=60.0)

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "+48505441635")

TOPIC_CHECK_PROMPT = """You analyze whether recent events/communications are related to an executed action.

Action that was executed:
- Type: {action_type}
- Description: {description}
- Executed at: {executed_at}
- Result: {result}

Recent events and communications are provided below.
Determine if any of them indicate:
- A direct response to the action
- Follow-up activity related to the action's topic
- Resolution of the issue the action addressed

Return JSON:
{{
  "related": true/false,
  "outcome": "success" | "partial" | "no_response",
  "evidence": "brief description of what you found, or null",
  "response_detected": true/false
}}

Be strict — only mark as "success" if there is clear evidence of a positive outcome.
Respond ONLY with JSON object."""

RECOMMENDATIONS_PROMPT = """Based on action outcome statistics, generate 3-5 actionable recommendations.

Statistics:
{stats}

Focus on:
- Which communication channels work best for which people
- Who is unresponsive and needs escalation
- Which action types have low success rates
- Time-of-day or day-of-week patterns

Return a JSON array of strings, each a concise recommendation in Polish.
Respond ONLY with JSON array."""


# ================================================================
# Database
# ================================================================

def _ensure_tables():
    """Create action_outcomes table if not exists."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS action_outcomes (
                    id BIGSERIAL PRIMARY KEY,
                    action_item_id BIGINT NOT NULL REFERENCES action_items(id),
                    check_type TEXT NOT NULL CHECK (check_type IN ('24h', '72h', '7d')),
                    outcome TEXT NOT NULL CHECK (outcome IN ('success', 'partial', 'no_response', 'failed', 'pending')),
                    evidence TEXT,
                    response_detected BOOLEAN DEFAULT FALSE,
                    response_time_hours NUMERIC,
                    auto_detected BOOLEAN DEFAULT TRUE,
                    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(action_item_id, check_type)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_action_outcomes_action
                ON action_outcomes(action_item_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_action_outcomes_outcome
                ON action_outcomes(outcome)
            """)
        conn.commit()


# ================================================================
# Core: find actions needing checks
# ================================================================

def get_actions_needing_check() -> list[dict]:
    """Find executed actions that need outcome checking."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ai.id, ai.action_type, ai.description, ai.draft_params,
                       ai.executed_at, ai.result
                FROM action_items ai
                WHERE ai.status = 'executed'
                  AND ai.executed_at IS NOT NULL
                  AND (
                    (ai.executed_at < NOW() - INTERVAL '24 hours'
                     AND ai.executed_at > NOW() - INTERVAL '48 hours'
                     AND NOT EXISTS (SELECT 1 FROM action_outcomes ao
                                     WHERE ao.action_item_id = ai.id AND ao.check_type = '24h'))
                    OR
                    (ai.executed_at < NOW() - INTERVAL '72 hours'
                     AND ai.executed_at > NOW() - INTERVAL '96 hours'
                     AND NOT EXISTS (SELECT 1 FROM action_outcomes ao
                                     WHERE ao.action_item_id = ai.id AND ao.check_type = '72h'))
                    OR
                    (ai.executed_at < NOW() - INTERVAL '7 days'
                     AND ai.executed_at > NOW() - INTERVAL '10 days'
                     AND NOT EXISTS (SELECT 1 FROM action_outcomes ao
                                     WHERE ao.action_item_id = ai.id AND ao.check_type = '7d'))
                  )
                ORDER BY ai.executed_at ASC
                LIMIT 20
            """)
            rows = cur.fetchall()

    actions = []
    for r in rows:
        params = r[3] if isinstance(r[3], dict) else (json.loads(r[3]) if r[3] else {})
        result_str = r[5] or ""
        actions.append({
            "id": r[0],
            "action_type": r[1],
            "description": r[2],
            "draft_params": params,
            "executed_at": r[4],
            "result": result_str,
        })
    return actions


def _determine_check_type(executed_at: datetime) -> str:
    """Determine which check type is needed based on execution time."""
    now = datetime.now(timezone.utc)
    elapsed = now - executed_at.replace(tzinfo=timezone.utc) if executed_at.tzinfo is None else now - executed_at
    hours = elapsed.total_seconds() / 3600

    if hours < 48:
        return "24h"
    elif hours < 96:
        return "72h"
    else:
        return "7d"


# ================================================================
# Check: email response
# ================================================================

def check_email_response(action: dict, check_type: str) -> dict:
    """For send_email actions: search incoming emails from the recipient in the time window."""
    params = action["draft_params"]
    recipient = params.get("to", "")
    executed_at = action["executed_at"]

    if not recipient:
        return {"outcome": "no_response", "evidence": "No recipient found in action params"}

    # Build search patterns from recipient email/name
    recipient_name = recipient.split("@")[0].replace(".", " ") if "@" in recipient else recipient
    search_patterns = [f"%{recipient}%", f"%{recipient_name}%"]

    # Determine time window
    check_windows = {"24h": 48, "72h": 96, "7d": 240}
    window_hours = check_windows.get(check_type, 48)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, LEFT(c.text, 300), d.created_at
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE s.source_type = 'email'
                  AND d.created_at > %s
                  AND d.created_at < %s + INTERVAL '%s hours'
                  AND (d.title ILIKE %s OR c.text ILIKE %s)
                LIMIT 5
            """, (executed_at, executed_at, window_hours, search_patterns[0], search_patterns[1]))
            matches = cur.fetchall()

    if matches:
        # Calculate response time from earliest match
        earliest_response = min(r[2] for r in matches)
        response_hours = None
        if earliest_response and executed_at:
            delta = earliest_response - executed_at
            response_hours = round(delta.total_seconds() / 3600, 1)

        evidence_texts = [f"[{str(r[2])[:16]}] {r[1][:150]}" for r in matches[:3]]
        return {
            "outcome": "success",
            "evidence": f"Found {len(matches)} response(s): " + "; ".join(evidence_texts),
            "response_detected": True,
            "response_time_hours": response_hours,
        }

    return {
        "outcome": "no_response",
        "evidence": f"No email response from {recipient} within {window_hours}h",
        "response_detected": False,
        "response_time_hours": None,
    }


# ================================================================
# Check: topic follow-up (LLM-based)
# ================================================================

def check_topic_follow_up(action: dict, check_type: str) -> dict:
    """For any action: check if related events appeared after execution using LLM."""
    executed_at = action["executed_at"]

    check_windows = {"24h": 48, "72h": 96, "7d": 240}
    window_hours = check_windows.get(check_type, 48)

    # Fetch recent events after execution
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.id, e.event_type, e.summary, e.event_time
                FROM events e
                WHERE (e.created_at > %s OR e.event_time > %s)
                  AND e.created_at < %s + INTERVAL '%s hours'
                ORDER BY e.created_at DESC
                LIMIT 30
            """, (executed_at, executed_at, executed_at, window_hours))
            events = [
                {"event_id": r[0], "type": r[1], "summary": r[2], "time": str(r[3]) if r[3] else None}
                for r in cur.fetchall()
            ]

            cur.execute("""
                SELECT c.id, LEFT(c.text, 300)
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE d.created_at > %s
                  AND d.created_at < %s + INTERVAL '%s hours'
                  AND length(c.text) > 100
                ORDER BY d.created_at DESC
                LIMIT 20
            """, (executed_at, executed_at, window_hours))
            chunks = [{"chunk_id": r[0], "text": r[1]} for r in cur.fetchall()]

    if not events and not chunks:
        return {
            "outcome": "no_response",
            "evidence": "No events or communications found in check window",
            "response_detected": False,
            "response_time_hours": None,
        }

    # Build context for LLM
    ctx_parts = ["=== RECENT EVENTS ==="]
    for ev in events:
        ctx_parts.append(f"[{ev['type']}] {ev['time'] or '?'}: {ev['summary']}")

    ctx_parts.append("\n=== RECENT COMMUNICATIONS ===")
    for ch in chunks:
        ctx_parts.append(f"[chunk {ch['chunk_id']}] {ch['text'][:250]}")

    context = "\n".join(ctx_parts)
    if len(context) > 12000:
        context = context[:12000] + "\n[truncated]"

    prompt = TOPIC_CHECK_PROMPT.format(
        action_type=action["action_type"],
        description=action["description"][:500],
        executed_at=str(action["executed_at"]),
        result=str(action["result"])[:300],
    )

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=500,
            temperature=0.1,
            system=[{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": context}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.action_outcome_tracker", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)

        return {
            "outcome": result.get("outcome", "no_response"),
            "evidence": result.get("evidence"),
            "response_detected": result.get("response_detected", False),
            "response_time_hours": None,
        }

    except Exception as e:
        log.error("topic_follow_up_check_error", action_id=action["id"], error=str(e))
        return {
            "outcome": "pending",
            "evidence": f"LLM check failed: {str(e)[:100]}",
            "response_detected": False,
            "response_time_hours": None,
        }


# ================================================================
# Check: open loop closure (7d only)
# ================================================================

def check_open_loop_closure(action: dict) -> dict:
    """For 7d checks: check if related open loops or commitments got resolved."""
    description_lower = action["description"].lower()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Check if any commitments related to this action got fulfilled
            cur.execute("""
                SELECT c.id, c.person_name, c.commitment_text, c.status
                FROM commitments c
                WHERE c.status = 'fulfilled'
                  AND c.updated_at > %s
                  AND (
                    LOWER(c.commitment_text) LIKE %s
                    OR LOWER(c.person_name) IN (
                        SELECT LOWER(value) FROM jsonb_each_text(%s::jsonb)
                        WHERE key IN ('to', 'assignee', 'attendee')
                    )
                  )
                LIMIT 5
            """, (
                action["executed_at"],
                f"%{description_lower[:50]}%",
                json.dumps(action["draft_params"], default=str),
            ))
            fulfilled = cur.fetchall()

            # Check if related events show resolution
            cur.execute("""
                SELECT e.id, e.event_type, e.summary
                FROM events e
                WHERE e.event_type IN ('decision', 'commitment_fulfilled', 'task_completed')
                  AND e.created_at > %s
                  AND LOWER(e.summary) LIKE %s
                LIMIT 5
            """, (action["executed_at"], f"%{description_lower[:50]}%"))
            resolved_events = cur.fetchall()

    if fulfilled or resolved_events:
        evidence_parts = []
        if fulfilled:
            evidence_parts.append(
                f"Fulfilled commitments: {', '.join(f'{r[1]}: {r[2][:80]}' for r in fulfilled)}"
            )
        if resolved_events:
            evidence_parts.append(
                f"Resolution events: {', '.join(f'[{r[1]}] {r[2][:80]}' for r in resolved_events)}"
            )
        return {
            "outcome": "success",
            "evidence": "; ".join(evidence_parts),
            "response_detected": True,
            "response_time_hours": None,
        }

    return {
        "outcome": "no_response",
        "evidence": "No open loop closure detected within 7 days",
        "response_detected": False,
        "response_time_hours": None,
    }


# ================================================================
# Save outcome
# ================================================================

def save_outcome(
    action_id: int,
    check_type: str,
    outcome: str,
    evidence: str | None,
    response_detected: bool,
    response_time_hours: float | None,
) -> None:
    """Insert into action_outcomes with ON CONFLICT DO UPDATE for idempotency."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO action_outcomes
                    (action_item_id, check_type, outcome, evidence,
                     response_detected, response_time_hours, checked_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (action_item_id, check_type)
                DO UPDATE SET
                    outcome = EXCLUDED.outcome,
                    evidence = EXCLUDED.evidence,
                    response_detected = EXCLUDED.response_detected,
                    response_time_hours = EXCLUDED.response_time_hours,
                    checked_at = NOW()
            """, (action_id, check_type, outcome, evidence, response_detected, response_time_hours))
        conn.commit()

    log.info("outcome_saved",
             action_id=action_id, check_type=check_type,
             outcome=outcome, response_detected=response_detected)


# ================================================================
# Effectiveness summary
# ================================================================

def get_action_effectiveness_summary(days: int = 30) -> dict:
    """Generate action effectiveness summary with per-type and per-person breakdowns."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Total executed actions in period
            cur.execute("""
                SELECT COUNT(*) FROM action_items
                WHERE status = 'executed'
                  AND executed_at > NOW() - INTERVAL '%s days'
            """, (days,))
            total_actions = cur.fetchone()[0]

            # Checked actions with outcomes
            cur.execute("""
                SELECT COUNT(DISTINCT ao.action_item_id)
                FROM action_outcomes ao
                JOIN action_items ai ON ai.id = ao.action_item_id
                WHERE ai.executed_at > NOW() - INTERVAL '%s days'
            """, (days,))
            checked = cur.fetchone()[0]

            # Success rate (from latest check per action)
            cur.execute("""
                SELECT ao.outcome, COUNT(*)
                FROM action_outcomes ao
                JOIN action_items ai ON ai.id = ao.action_item_id
                WHERE ai.executed_at > NOW() - INTERVAL '%s days'
                  AND ao.check_type = (
                      SELECT MAX(ao2.check_type) FROM action_outcomes ao2
                      WHERE ao2.action_item_id = ao.action_item_id
                  )
                GROUP BY ao.outcome
            """, (days,))
            outcome_counts = {r[0]: r[1] for r in cur.fetchall()}

            total_outcomes = sum(outcome_counts.values())
            success_count = outcome_counts.get("success", 0) + outcome_counts.get("partial", 0)
            success_rate = round(success_count / total_outcomes, 3) if total_outcomes > 0 else None

            # Average response time
            cur.execute("""
                SELECT AVG(ao.response_time_hours)
                FROM action_outcomes ao
                JOIN action_items ai ON ai.id = ao.action_item_id
                WHERE ai.executed_at > NOW() - INTERVAL '%s days'
                  AND ao.response_time_hours IS NOT NULL
            """, (days,))
            avg_response_row = cur.fetchone()
            avg_response_time = round(float(avg_response_row[0]), 1) if avg_response_row and avg_response_row[0] else None

            # By action type
            cur.execute("""
                SELECT ai.action_type,
                       COUNT(*) as total,
                       COUNT(*) FILTER (WHERE ao.outcome = 'success') as success,
                       COUNT(*) FILTER (WHERE ao.outcome = 'no_response') as no_response,
                       COUNT(*) FILTER (WHERE ao.outcome = 'partial') as partial,
                       COUNT(*) FILTER (WHERE ao.outcome = 'failed') as failed
                FROM action_items ai
                LEFT JOIN action_outcomes ao ON ao.action_item_id = ai.id
                WHERE ai.status = 'executed'
                  AND ai.executed_at > NOW() - INTERVAL '%s days'
                GROUP BY ai.action_type
                ORDER BY total DESC
            """, (days,))
            by_type = {}
            for r in cur.fetchall():
                by_type[r[0]] = {
                    "total": r[1], "success": r[2],
                    "no_response": r[3], "partial": r[4], "failed": r[5],
                }

            # By person (extract from draft_params)
            cur.execute("""
                SELECT
                    COALESCE(
                        ai.draft_params->>'to',
                        ai.draft_params->>'assignee',
                        'unknown'
                    ) as person,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE ao.outcome = 'success') as success,
                    COUNT(*) FILTER (WHERE ao.outcome = 'no_response') as no_response,
                    AVG(ao.response_time_hours) FILTER (WHERE ao.response_time_hours IS NOT NULL) as avg_hours
                FROM action_items ai
                LEFT JOIN action_outcomes ao ON ao.action_item_id = ai.id
                WHERE ai.status = 'executed'
                  AND ai.executed_at > NOW() - INTERVAL '%s days'
                GROUP BY person
                HAVING COUNT(*) >= 2
                ORDER BY total DESC
            """, (days,))
            by_person = {}
            for r in cur.fetchall():
                person_key = r[0]
                total_p = r[1]
                success_p = r[2]
                by_person[person_key] = {
                    "success_rate": round(success_p / total_p, 2) if total_p > 0 else None,
                    "avg_response_hours": round(float(r[4]), 1) if r[4] else None,
                    "total": total_p,
                    "no_response": r[3],
                }

    # Generate recommendations using LLM
    recommendations = _generate_recommendations(by_type, by_person, success_rate, avg_response_time)

    return {
        "total_actions": total_actions,
        "checked": checked,
        "success_rate": success_rate,
        "avg_response_time_hours": avg_response_time,
        "by_action_type": by_type,
        "by_person": by_person,
        "recommendations": recommendations,
    }


def _generate_recommendations(
    by_type: dict, by_person: dict,
    success_rate: float | None, avg_response_time: float | None,
) -> list[str]:
    """Use LLM to generate actionable recommendations from outcome patterns."""
    stats = {
        "success_rate": success_rate,
        "avg_response_time_hours": avg_response_time,
        "by_action_type": by_type,
        "by_person": by_person,
    }

    # Skip LLM if no data
    if not by_type and not by_person:
        return []

    prompt = RECOMMENDATIONS_PROMPT.format(stats=json.dumps(stats, ensure_ascii=False, default=str, indent=2))

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=500,
            temperature=0.3,
            system=[{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": "Generate recommendations based on these action outcome statistics."}],
        )

        if hasattr(response, "usage"):
            log_anthropic_cost(ANTHROPIC_MODEL, "analysis.action_outcome_tracker.recommendations", response.usage)

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)

    except Exception as e:
        log.error("recommendations_generation_error", error=str(e))
        return []


# ================================================================
# Main pipeline
# ================================================================

def run_outcome_checks() -> dict:
    """Main pipeline: get actions needing check, check each, save outcomes, return summary."""
    log.info("outcome_checks_start")
    _ensure_tables()

    actions = get_actions_needing_check()
    log.info("actions_needing_check", count=len(actions))

    results = []
    no_response_by_person: dict[str, int] = {}

    for action in actions:
        check_type = _determine_check_type(action["executed_at"])
        action_type = action["action_type"]

        log.info("checking_action",
                 action_id=action["id"], action_type=action_type, check_type=check_type)

        # Choose check strategy based on action type and check type
        if action_type == "send_email":
            result = check_email_response(action, check_type)
        elif check_type == "7d":
            result = check_open_loop_closure(action)
        else:
            result = check_topic_follow_up(action, check_type)

        # Save outcome
        save_outcome(
            action_id=action["id"],
            check_type=check_type,
            outcome=result["outcome"],
            evidence=result.get("evidence"),
            response_detected=result.get("response_detected", False),
            response_time_hours=result.get("response_time_hours"),
        )

        # Track no_response for alert logic
        if result["outcome"] == "no_response":
            person = action["draft_params"].get("to") or action["draft_params"].get("assignee") or "unknown"
            no_response_by_person[person] = no_response_by_person.get(person, 0) + 1

        results.append({
            "action_id": action["id"],
            "check_type": check_type,
            "outcome": result["outcome"],
            "response_detected": result.get("response_detected", False),
        })

    # Check for repeated failures
    actions_with_no_response = [
        {"person": person, "count": count}
        for person, count in no_response_by_person.items()
        if count >= 3
    ]
    if actions_with_no_response:
        notify_failures(actions_with_no_response)

    summary = {
        "status": "ok",
        "actions_checked": len(results),
        "outcomes": results,
        "repeated_no_response": actions_with_no_response,
    }

    log.info("outcome_checks_complete",
             checked=len(results),
             no_response_alerts=len(actions_with_no_response))
    return summary


# ================================================================
# Failure notifications
# ================================================================

def notify_failures(actions_with_no_response: list[dict]) -> None:
    """If 3+ consecutive no_response from same person, WhatsApp alert to Sebastian."""
    for entry in actions_with_no_response:
        person = entry["person"]
        count = entry["count"]
        msg = (
            f"[Gilbertus] Brak odpowiedzi od {person} "
            f"na {count} akcji z rzadu. Rozważ eskalację lub zmianę kanału."
        )
        log.warning("repeated_no_response", person=person, count=count)
        try:
            subprocess.run(
                [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
                 "--target", WA_TARGET, "--message", msg],
                capture_output=True, text=True, timeout=30,
            )
        except Exception:
            pass


# ================================================================
# CLI
# ================================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        result = get_action_effectiveness_summary(days=days)
    else:
        result = run_outcome_checks()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
