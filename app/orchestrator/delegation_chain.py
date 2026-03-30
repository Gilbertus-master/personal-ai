"""
Delegation Chain — Gilbertus delegates tasks through Omnius, tracks execution, escalates.

Full flow:
1. Gilbertus detects actionable item (overdue commitment, new task, opportunity)
2. Checks authority level -> auto-delegate if level 0-1
3. Creates task in Omnius (create_ticket or assign_task)
4. Tracks execution status via periodic checks
5. Sends reminders if not started within 24h
6. Escalates to Sebastian if overdue

Cron: every 4h — check status of delegated tasks
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "+48505441635")


# ================================================================
# Database
# ================================================================

_tables_ensured = False
def _ensure_tables():
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS delegation_tasks (
                    id BIGSERIAL PRIMARY KEY,
                    commitment_id BIGINT,
                    action_item_id BIGINT REFERENCES action_items(id),
                    omnius_tenant TEXT,
                    omnius_ticket_id TEXT,
                    assignee TEXT NOT NULL,
                    assignee_email TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    deadline TIMESTAMPTZ,
                    priority TEXT DEFAULT 'medium'
                        CHECK (priority IN ('low', 'medium', 'high', 'critical')),
                    status TEXT NOT NULL DEFAULT 'assigned'
                        CHECK (status IN (
                            'assigned', 'reminded', 'in_progress',
                            'completed', 'escalated', 'failed', 'cancelled'
                        )),
                    check_count INT DEFAULT 0,
                    last_checked TIMESTAMPTZ,
                    escalation_level INT DEFAULT 0,
                    reminder_sent BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,
                    result TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_deleg_status
                    ON delegation_tasks(status);
                CREATE INDEX IF NOT EXISTS idx_deleg_assignee
                    ON delegation_tasks(assignee);
                CREATE INDEX IF NOT EXISTS idx_deleg_deadline
                    ON delegation_tasks(deadline)
                    WHERE status IN ('assigned', 'reminded', 'in_progress');
            """)
        conn.commit()
    _tables_ensured = True


# ================================================================
# Core: delegate_task
# ================================================================

def delegate_task(
    assignee: str,
    title: str,
    description: str = "",
    deadline: str | None = None,
    priority: str = "medium",
    commitment_id: int | None = None,
    omnius_tenant: str | None = None,
) -> dict[str, Any]:
    """Create a delegation task and optionally push to Omnius."""
    _ensure_tables()

    deadline_ts = None
    if deadline:
        try:
            deadline_ts = datetime.fromisoformat(deadline)
            if deadline_ts.tzinfo is None:
                deadline_ts = deadline_ts.replace(tzinfo=timezone.utc)
        except ValueError:
            log.warning("delegation.invalid_deadline", deadline=deadline)

    omnius_ticket_id = None
    if omnius_tenant:
        try:
            from app.omnius.client import get_omnius
            client = get_omnius(omnius_tenant)
            ticket = client.assign_task(
                assignee=assignee,
                title=title,
                description=description,
                deadline=deadline,
                priority=priority,
            )
            omnius_ticket_id = str(ticket.get("ticket_id", ""))
            log.info("delegation.omnius_ticket_created",
                     tenant=omnius_tenant, ticket_id=omnius_ticket_id)
        except Exception as exc:
            log.warning("delegation.omnius_failed", tenant=omnius_tenant, error=str(exc))

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO delegation_tasks
                    (commitment_id, omnius_tenant, omnius_ticket_id,
                     assignee, title, description, deadline, priority)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                commitment_id, omnius_tenant, omnius_ticket_id,
                assignee, title, description, deadline_ts, priority,
            ))
            task_id = cur.fetchall()[0][0]
        conn.commit()

    log.info("delegation.created",
             task_id=task_id, assignee=assignee, title=title, priority=priority)

    return {
        "task_id": task_id,
        "assignee": assignee,
        "title": title,
        "deadline": str(deadline_ts) if deadline_ts else None,
        "priority": priority,
        "omnius_ticket_id": omnius_ticket_id,
        "status": "assigned",
    }


# ================================================================
# Cron: check_delegation_status
# ================================================================

def check_delegation_status() -> dict[str, Any]:
    """Main cron function. Check all active delegations, remind, escalate."""
    _ensure_tables()
    results = {"checked": 0, "reminded": 0, "escalated": 0, "completed": 0}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, assignee, assignee_email, title, description, deadline,
                       priority, status, check_count, reminder_sent, created_at
                FROM delegation_tasks
                WHERE status IN ('assigned', 'reminded', 'in_progress')
                ORDER BY deadline ASC NULLS LAST
            """)
            tasks = cur.fetchall()

    now = datetime.now(timezone.utc)
    for task in tasks:
        (task_id, assignee, email, title, desc,
         deadline, priority, status, checks, reminded, created) = task
        results["checked"] += 1

        # Check for completion evidence in recent events
        evidence = _check_completion_evidence(task_id, assignee, title)
        if evidence:
            _mark_completed(task_id, evidence)
            results["completed"] += 1
            continue

        hours_since_created = (now - created).total_seconds() / 3600

        # Send reminder after 24h if not started
        if status == "assigned" and hours_since_created > 24 and not reminded:
            _send_reminder(task_id, assignee, email, title)
            results["reminded"] += 1

        # Escalate if deadline approaching or passed
        if deadline:
            hours_until_deadline = (deadline - now).total_seconds() / 3600
            if hours_until_deadline < 0:
                _escalate(task_id, assignee, title, deadline, "overdue")
                results["escalated"] += 1
            elif hours_until_deadline < 24 and status != "in_progress":
                _escalate(task_id, assignee, title, deadline, "deadline_approaching")
                results["escalated"] += 1

        # Update check count
        _update_check(task_id)

    log.info("delegation.check_complete", **results)
    return results


# ================================================================
# Helpers
# ================================================================

def _check_completion_evidence(task_id: int, assignee: str, title: str) -> str | None:
    """Search recent events/chunks for evidence that the task was completed."""
    keywords = [w.lower() for w in re.split(r'\s+', title) if len(w) > 3]
    if not keywords:
        return None

    # Build keyword filter — match any 2 keywords in event description
    keyword_conditions = " OR ".join(
        ["LOWER(e.description) LIKE %s"] * len(keywords)
    )
    params: list[Any] = [f"%{kw}%" for kw in keywords]
    params.append(assignee)

    query = (
            "SELECT e.description, e.event_date FROM events e "
            "WHERE (" + keyword_conditions + ") "
            "AND LOWER(e.person_name) = LOWER(%s) "
            "AND e.event_date > NOW() - INTERVAL '7 days' "
            "AND e.event_type IN ('commitment_made', 'task_completed', "
            "                     'decision_made', 'deliverable') "
            "ORDER BY e.event_date DESC LIMIT 3"
        )

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        if rows:
            evidence_parts = [f"{row[0]} ({row[1]})" for row in rows]
            return "Evidence: " + "; ".join(evidence_parts)
    except Exception as exc:
        log.warning("delegation.evidence_check_failed", task_id=task_id, error=str(exc))

    return None


def _send_reminder(task_id: int, assignee: str, email: str | None, title: str):
    """Send reminder to assignee via Teams or WhatsApp."""
    body = f"Przypomnienie: zadanie '{title}' oczekuje na realizację."

    try:
        from app.orchestrator.communication import send_and_log
        send_and_log(
            channel="teams" if email else "whatsapp",
            recipient=email or assignee,
            subject=None,
            body=body,
            authorization_type="delegation_reminder",
        )
        log.info("delegation.reminder_sent", task_id=task_id, assignee=assignee)
    except Exception as exc:
        log.warning("delegation.reminder_failed", task_id=task_id, error=str(exc))

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE delegation_tasks SET reminder_sent = TRUE, status = 'reminded' WHERE id = %s",
                (task_id,),
            )
        conn.commit()


def _escalate(task_id: int, assignee: str, title: str, deadline: datetime, reason: str):
    """Escalate to Sebastian via WhatsApp."""
    deadline_str = deadline.strftime("%Y-%m-%d %H:%M") if deadline else "brak"
    reason_pl = {
        "overdue": "Przekroczony deadline",
        "deadline_approaching": "Deadline w ciagu 24h, zadanie nierozpoczete",
    }.get(reason, reason)

    msg = (
        f"\u26a0\ufe0f *Eskalacja delegacji #{task_id}*\n"
        f"Zadanie: {title}\n"
        f"Przypisane do: {assignee}\n"
        f"Deadline: {deadline_str}\n"
        f"Powod: {reason_pl}\n"
        f"\n"
        f"Odpowiedz:\n"
        f"  remind #{task_id} \u2014 wyslij ponowne przypomnienie\n"
        f"  cancel #{task_id} \u2014 anuluj zadanie\n"
        f"  extend #{task_id} [dni] \u2014 przedluz deadline"
    )

    try:
        subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", WA_TARGET, "--message", msg],
            capture_output=True, text=True, timeout=30,
        )
        log.info("delegation.escalated", task_id=task_id, reason=reason)
    except Exception as exc:
        log.warning("delegation.escalation_failed", task_id=task_id, error=str(exc))

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE delegation_tasks
                SET status = 'escalated', escalation_level = escalation_level + 1
                WHERE id = %s
            """, (task_id,))
        conn.commit()


def _mark_completed(task_id: int, evidence: str):
    """Mark delegation as completed and update linked commitment if any."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE delegation_tasks
                SET status = 'completed', completed_at = NOW(), result = %s
                WHERE id = %s
                RETURNING commitment_id
            """, (evidence, task_id))
            rows = cur.fetchall()
            row = rows[0] if rows else None

            # Update linked commitment
            if row and row[0]:
                cur.execute(
                    "UPDATE commitments SET status = 'fulfilled' WHERE id = %s",
                    (row[0],),
                )
        conn.commit()

    log.info("delegation.completed", task_id=task_id)


def _update_check(task_id: int):
    """Increment check_count and update last_checked."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE delegation_tasks SET check_count = check_count + 1, last_checked = NOW() WHERE id = %s",
                (task_id,),
            )
        conn.commit()


# ================================================================
# Dashboard
# ================================================================

def get_delegation_dashboard() -> dict[str, Any]:
    """Return delegation stats for display."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # By status
            cur.execute("""
                SELECT status, COUNT(*) FROM delegation_tasks GROUP BY status
            """)
            by_status = {row[0]: row[1] for row in cur.fetchall()}

            # By assignee
            cur.execute("""
                SELECT assignee, status, COUNT(*)
                FROM delegation_tasks
                GROUP BY assignee, status
            """)
            by_assignee: dict[str, dict[str, int]] = {}
            for assignee, status, cnt in cur.fetchall():
                if assignee not in by_assignee:
                    by_assignee[assignee] = {"active": 0, "completed": 0, "escalated": 0}
                if status in ("assigned", "reminded", "in_progress"):
                    by_assignee[assignee]["active"] += cnt
                elif status == "completed":
                    by_assignee[assignee]["completed"] += cnt
                elif status == "escalated":
                    by_assignee[assignee]["escalated"] += cnt

            # Overdue
            cur.execute("""
                SELECT id, title, assignee, deadline
                FROM delegation_tasks
                WHERE status IN ('assigned', 'reminded', 'in_progress', 'escalated')
                  AND deadline < NOW()
                ORDER BY deadline ASC
            """)
            overdue = [
                {"id": r[0], "title": r[1], "assignee": r[2],
                 "days_overdue": (datetime.now(timezone.utc) - r[3]).days if r[3] else 0}
                for r in cur.fetchall()
            ]

            # Upcoming deadlines (next 7 days)
            cur.execute("""
                SELECT id, title, assignee, deadline
                FROM delegation_tasks
                WHERE status IN ('assigned', 'reminded', 'in_progress')
                  AND deadline BETWEEN NOW() AND NOW() + INTERVAL '7 days'
                ORDER BY deadline ASC
            """)
            upcoming = [
                {"id": r[0], "title": r[1], "assignee": r[2], "deadline": str(r[3])}
                for r in cur.fetchall()
            ]

            # Completion rate
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                    COUNT(*) FILTER (WHERE status IN ('completed', 'failed', 'cancelled')) AS total
                FROM delegation_tasks
            """)
            comp_row = cur.fetchone()
            completed_n = comp_row[0] if comp_row else 0
            total_closed = comp_row[1] if comp_row else 0
            completion_rate = (completed_n / total_closed) if total_closed > 0 else 0.0

            # Avg completion days
            cur.execute("""
                SELECT AVG(EXTRACT(EPOCH FROM (completed_at - created_at)) / 86400)
                FROM delegation_tasks
                WHERE status = 'completed' AND completed_at IS NOT NULL
            """)
            avg_row = cur.fetchone()
            avg_days = round(avg_row[0], 1) if avg_row and avg_row[0] else 0.0

    active_statuses = ("assigned", "reminded", "in_progress", "escalated")
    active_count = sum(by_status.get(s, 0) for s in active_statuses)

    return {
        "active": active_count,
        "by_status": by_status,
        "by_assignee": by_assignee,
        "overdue": overdue,
        "upcoming_deadlines": upcoming,
        "completion_rate": round(completion_rate, 2),
        "avg_completion_days": avg_days,
    }


# ================================================================
# WhatsApp command handler
# ================================================================

def handle_delegation_command(text: str, sender_phone: str = "") -> dict[str, Any] | None:
    """Handle WhatsApp commands: remind #ID, cancel #ID, extend #ID [days]."""
    from app.orchestrator.task_monitor import AUTHORIZED_SENDERS
    if AUTHORIZED_SENDERS and sender_phone not in AUTHORIZED_SENDERS:
        log.warning("delegation_unauthorized_sender",
                     sender=sender_phone, text=text[:50])
        return None

    text = text.strip().lower()

    # remind #ID
    m = re.match(r'remind\s+#?(\d+)', text)
    if m:
        task_id = int(m.group(1))
        return _handle_remind(task_id)

    # cancel #ID
    m = re.match(r'cancel\s+#?(\d+)', text)
    if m:
        task_id = int(m.group(1))
        return _handle_cancel(task_id)

    # extend #ID [days]
    m = re.match(r'extend\s+#?(\d+)\s+(\d+)', text)
    if m:
        task_id = int(m.group(1))
        days = int(m.group(2))
        return _handle_extend(task_id, days)

    return None


def _handle_remind(task_id: int) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT assignee, assignee_email, title FROM delegation_tasks WHERE id = %s",
                (task_id,),
            )
            rows = cur.fetchall()
            if not rows:
                return {"error": f"Delegation #{task_id} not found"}
            assignee, email, title = rows[0]

    _send_reminder(task_id, assignee, email, title)
    return {"task_id": task_id, "action": "reminded", "assignee": assignee}


def _handle_cancel(task_id: int) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE delegation_tasks SET status = 'cancelled' WHERE id = %s AND status NOT IN ('completed', 'cancelled')",
                (task_id,),
            )
            if cur.rowcount == 0:
                conn.rollback()
                return {"error": f"Delegation #{task_id} not found or already closed"}
        conn.commit()
    log.info("delegation.cancelled", task_id=task_id)
    return {"task_id": task_id, "action": "cancelled"}


def _handle_extend(task_id: int, days: int) -> dict[str, Any]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE delegation_tasks
                SET deadline = COALESCE(deadline, NOW()) + %s * INTERVAL '1 day',
                    status = CASE WHEN status = 'escalated' THEN 'assigned' ELSE status END,
                    escalation_level = 0
                WHERE id = %s AND status NOT IN ('completed', 'cancelled')
                RETURNING deadline
            """, (days, task_id))
            rows = cur.fetchall()
            if not rows:
                conn.rollback()
                return {"error": f"Delegation #{task_id} not found or already closed"}
            new_deadline = rows[0][0]
        conn.commit()

    log.info("delegation.extended", task_id=task_id, days=days, new_deadline=str(new_deadline))
    return {"task_id": task_id, "action": "extended", "new_deadline": str(new_deadline), "days_added": days}


# ================================================================
# Auto-delegate overdue commitments
# ================================================================

def auto_delegate_overdue_commitments() -> list[dict[str, Any]]:
    """Find overdue commitments not yet delegated and create delegation tasks."""
    _ensure_tables()
    delegated = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.person_name, c.commitment_text, c.deadline
                FROM commitments c
                WHERE c.status = 'overdue'
                  AND NOT EXISTS (
                      SELECT 1 FROM delegation_tasks dt
                      WHERE dt.commitment_id = c.id
                        AND dt.status NOT IN ('completed', 'cancelled', 'failed')
                  )
                LIMIT 10
            """)
            overdue = cur.fetchall()

    for cid, person, text, deadline in overdue:
        result = delegate_task(
            assignee=person,
            title=text[:200],
            description=f"Auto-delegated from overdue commitment #{cid}",
            deadline=str(deadline) if deadline else None,
            priority="high",
            commitment_id=cid,
        )
        delegated.append(result)
        log.info("delegation.auto_delegated", commitment_id=cid, assignee=person)

    return delegated


# ================================================================
# CLI
# ================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--dashboard":
        result = get_delegation_dashboard()
    elif len(sys.argv) > 1 and sys.argv[1] == "--auto-delegate":
        result = auto_delegate_overdue_commitments()
    else:
        result = check_delegation_status()

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
