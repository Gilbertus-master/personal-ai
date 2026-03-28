"""
Training Manager — tworzenie, przypisywanie i tracking szkoleń compliance.

Workflow:
1. Tworzenie szkolenia (na bazie matter/obligation)
2. Generacja materiałów (via document_generator jeśli potrzebne)
3. Przypisanie do osób (wg target_audience)
4. Notyfikacja (WhatsApp/email)
5. Tracking completions
6. Reminders dla overdue
7. Raportowanie (kto przeszedł, kto nie)
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import os
import subprocess
from datetime import date, datetime, timedelta
from typing import Any

from app.db.postgres import get_pg_connection
from dotenv import load_dotenv

load_dotenv()

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "")


# ---------------------------------------------------------------------------
# Training CRUD
# ---------------------------------------------------------------------------

def create_training(
    title: str,
    area_code: str,
    matter_id: int | None = None,
    training_type: str = "mandatory",
    content_summary: str | None = None,
    target_audience: list[str] | None = None,
    deadline: str | None = None,
    generate_material: bool = False,
) -> dict[str, Any]:
    """Create a compliance training, optionally generate material and assign."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # 1. Resolve area_id
            cur.execute("SELECT id FROM compliance_areas WHERE code = %s", (area_code,))
            row = cur.fetchone()
            if not row:
                return {"error": "area_not_found", "area_code": area_code}
            area_id = row[0]

            # 2. Insert training
            cur.execute("""
                INSERT INTO compliance_trainings
                    (title, area_id, matter_id, training_type, content_summary,
                     target_audience, deadline, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'planned')
                RETURNING id
            """, (
                title, area_id, matter_id, training_type, content_summary,
                target_audience, deadline,
            ))
            training_id = cur.fetchone()[0]
        conn.commit()

    log.info("training_created", training_id=training_id, title=title, area_code=area_code)

    # 3. Generate material if requested
    if generate_material and matter_id:
        try:
            from app.analysis.legal.document_generator import generate_document
            doc = generate_document(
                matter_id, "training_material", title=f"Szkolenie: {title}",
            )
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE compliance_trainings
                        SET content_document_id = %s, status = 'material_ready'
                        WHERE id = %s
                    """, (doc["document_id"], training_id))
                conn.commit()
            log.info("training_material_generated", training_id=training_id, doc_id=doc["document_id"])
        except Exception as exc:
            log.warning("training_material_failed", training_id=training_id, error=str(exc))

    # 4. Assign to audience
    assigned_count = 0
    if target_audience:
        assigned_count = assign_training_to_audience(training_id, target_audience)

    return {
        "training_id": training_id,
        "title": title,
        "status": "planned",
        "assigned_count": assigned_count,
    }


def assign_training_to_audience(training_id: int, target_audience: list[str]) -> int:
    """Assign training to people based on audience groups and create delegation tasks."""
    # Fetch training info
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.title, t.deadline
                FROM compliance_trainings t
                WHERE t.id = %s
            """, (training_id,))
            row = cur.fetchone()
    if not row:
        return 0
    training_title, raw_deadline = row
    deadline = str(raw_deadline) if raw_deadline else None

    # Resolve person IDs per audience group
    person_ids: set[int] = set()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for group in target_audience:
                group_lower = group.strip().lower()
                if group_lower == "all_employees":
                    cur.execute("SELECT id FROM people")
                elif group_lower == "management":
                    cur.execute("""
                        SELECT DISTINCT p.id FROM people p
                        JOIN employee_work_profiles ewp ON ewp.person_id = p.id
                        WHERE ewp.position ILIKE '%%dyrektor%%'
                           OR ewp.position ILIKE '%%prezes%%'
                           OR ewp.position ILIKE '%%kierownik%%'
                           OR ewp.position ILIKE '%%manager%%'
                    """)
                elif group_lower == "traders":
                    cur.execute("""
                        SELECT DISTINCT p.id FROM people p
                        JOIN employee_work_profiles ewp ON ewp.person_id = p.id
                        WHERE ewp.position ILIKE '%%trader%%'
                           OR ewp.position ILIKE '%%trading%%'
                           OR ewp.department ILIKE '%%trading%%'
                    """)
                elif group_lower == "it":
                    cur.execute("""
                        SELECT DISTINCT p.id FROM people p
                        JOIN employee_work_profiles ewp ON ewp.person_id = p.id
                        WHERE ewp.department ILIKE '%%it%%'
                           OR ewp.position ILIKE '%%it%%'
                           OR ewp.position ILIKE '%%developer%%'
                           OR ewp.position ILIKE '%%admin%%system%%'
                    """)
                else:
                    # Treat as person name search
                    cur.execute("""
                        SELECT id FROM people
                        WHERE first_name || ' ' || last_name ILIKE %s
                    """, (f"%{group}%",))
                rows = cur.fetchall()
                person_ids.update(r[0] for r in rows)

    if not person_ids:
        # Fallback: if employee_work_profiles doesn't exist, get all people
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM people")
                person_ids = {r[0] for r in cur.fetchall()}

    # Assign each person
    assigned = 0
    for pid in person_ids:
        try:
            _assign_person(training_id, pid, training_title, deadline)
            assigned += 1
        except Exception as exc:
            log.warning("training_assign_failed", training_id=training_id, person_id=pid, error=str(exc))

    # Update training status
    if assigned > 0:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE compliance_trainings
                    SET status = 'in_progress'
                    WHERE id = %s AND status IN ('planned', 'material_ready', 'scheduled')
                """, (training_id,))
            conn.commit()

    log.info("training_assigned", training_id=training_id, assigned=assigned, audience=target_audience)
    return assigned


def _assign_person(training_id: int, person_id: int, training_title: str, deadline: str | None) -> None:
    """Assign training to a single person: create record, delegation task, notify."""
    # Get person name
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT first_name, last_name FROM people WHERE id = %s", (person_id,))
            prow = cur.fetchone()
    if not prow:
        return
    person_name = f"{prow[0]} {prow[1]}"

    # Check if already assigned
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM compliance_training_records
                WHERE training_id = %s AND person_id = %s
            """, (training_id, person_id))
            if cur.fetchone():
                return  # Already assigned

    # Create delegation task
    delegation_task_id = None
    try:
        from app.orchestrator.delegation_chain import delegate_task
        result = delegate_task(
            assignee=person_name,
            title=f"Szkolenie compliance: {training_title}",
            description=f"Ukończ szkolenie: {training_title}. Deadline: {deadline or 'brak'}",
            deadline=deadline,
            priority="medium",
        )
        delegation_task_id = result.get("task_id")
    except Exception as exc:
        log.warning("delegation_task_failed", person=person_name, error=str(exc))

    # Insert training record
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO compliance_training_records
                    (training_id, person_id, status, notified_at, delegation_task_id)
                VALUES (%s, %s, 'notified', NOW(), %s)
                RETURNING id
            """, (training_id, person_id, delegation_task_id))
        conn.commit()

    log.info("person_assigned_training", person=person_name, training_id=training_id)


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------

def complete_training(training_id: int, person_id: int, score: float | None = None) -> dict[str, Any]:
    """Mark training as completed for a person."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # 1. Update training record
            cur.execute("""
                UPDATE compliance_training_records
                SET status = 'completed', completed_at = NOW(), score = %s
                WHERE training_id = %s AND person_id = %s
                RETURNING delegation_task_id
            """, (score, training_id, person_id))
            row = cur.fetchone()
            if not row:
                return {"error": "record_not_found", "training_id": training_id, "person_id": person_id}

            # 2. Complete delegation task if exists
            delegation_task_id = row[0]
            if delegation_task_id:
                cur.execute("""
                    UPDATE delegation_tasks
                    SET status = 'completed', completed_at = NOW()
                    WHERE id = %s AND status != 'completed'
                """, (delegation_task_id,))

            # 3. Check if all people completed
            cur.execute("""
                SELECT COUNT(*) FILTER (WHERE status != 'completed' AND status != 'exempted') AS pending,
                       COUNT(*) AS total
                FROM compliance_training_records
                WHERE training_id = %s
            """, (training_id,))
            counts = cur.fetchone()
            all_completed = counts[0] == 0

            if all_completed:
                cur.execute("""
                    UPDATE compliance_trainings
                    SET status = 'completed'
                    WHERE id = %s
                """, (training_id,))

        conn.commit()

    log.info("training_completed", training_id=training_id, person_id=person_id, all_completed=all_completed)
    return {
        "training_id": training_id,
        "person_id": person_id,
        "status": "completed",
        "all_completed": all_completed,
    }


# ---------------------------------------------------------------------------
# Status & reporting
# ---------------------------------------------------------------------------

def get_training_status(training_id: int) -> dict[str, Any]:
    """Get training status with per-person breakdown."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.title, t.deadline, t.status, t.training_type
                FROM compliance_trainings t
                WHERE t.id = %s
            """, (training_id,))
            trow = cur.fetchone()
            if not trow:
                return {"error": "training_not_found", "training_id": training_id}

            title, deadline, t_status, t_type = trow

            cur.execute("""
                SELECT tr.status, p.first_name, p.last_name, tr.completed_at, tr.score
                FROM compliance_training_records tr
                JOIN people p ON p.id = tr.person_id
                WHERE tr.training_id = %s
                ORDER BY tr.status, p.last_name
            """, (training_id,))
            records = cur.fetchall()

    people = []
    status_counts: dict[str, int] = {}
    for rec in records:
        st, fn, ln, completed_at, sc = rec
        status_counts[st] = status_counts.get(st, 0) + 1
        people.append({
            "name": f"{fn} {ln}",
            "status": st,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "score": float(sc) if sc is not None else None,
        })

    today = date.today()
    overdue = 0
    if deadline and isinstance(deadline, (date, datetime)):
        dl = deadline if isinstance(deadline, date) else deadline.date()
        if dl < today:
            overdue = status_counts.get("assigned", 0) + status_counts.get("notified", 0) + status_counts.get("started", 0)

    return {
        "training_id": training_id,
        "title": title,
        "deadline": str(deadline) if deadline else None,
        "training_type": t_type,
        "status": t_status,
        "total": len(records),
        "completed": status_counts.get("completed", 0),
        "overdue": overdue,
        "pending": len(records) - status_counts.get("completed", 0) - status_counts.get("exempted", 0),
        "people": people,
    }


# ---------------------------------------------------------------------------
# Deadline checking (cron)
# ---------------------------------------------------------------------------

def check_training_deadlines() -> dict[str, Any]:
    """Cron: check training deadlines, mark overdue, send reminders."""
    today = date.today()
    reminder_horizon = today + timedelta(days=7)
    overdue_marked = 0
    reminders_sent = 0

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # 1. Mark overdue records
            cur.execute("""
                UPDATE compliance_training_records tr
                SET status = 'overdue'
                FROM compliance_trainings t
                WHERE tr.training_id = t.id
                  AND t.deadline < %s
                  AND t.status != 'completed'
                  AND tr.status IN ('assigned', 'notified', 'started')
                RETURNING tr.id
            """, (today,))
            overdue_marked = cur.rowcount

            # 2. Find trainings with deadline in next 7 days needing reminders
            cur.execute("""
                SELECT t.id, t.title, t.deadline, p.first_name, p.last_name
                FROM compliance_training_records tr
                JOIN compliance_trainings t ON t.id = tr.training_id
                JOIN people p ON p.id = tr.person_id
                WHERE t.deadline BETWEEN %s AND %s
                  AND t.status != 'completed'
                  AND tr.status IN ('assigned', 'notified')
            """, (today, reminder_horizon))
            remind_rows = cur.fetchall()

        conn.commit()

    # Send WhatsApp reminders
    for tid, title, deadline, fn, ln in remind_rows:
        msg = (
            f"\U0001F4DA *Reminder: Szkolenie compliance*\n"
            f"{title}\n"
            f"Termin: {deadline}\n"
            f"Status: nie ukończone"
        )
        try:
            if WA_TARGET:
                subprocess.run(
                    [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
                     "--target", WA_TARGET, "--message", msg],
                    capture_output=True, text=True, timeout=30,
                )
                reminders_sent += 1
        except Exception as exc:
            log.warning("reminder_send_failed", person=f"{fn} {ln}", error=str(exc))

    log.info("training_deadlines_checked",
             overdue_marked=overdue_marked, reminders_sent=reminders_sent)
    return {
        "checked": True,
        "overdue_marked": overdue_marked,
        "reminders_sent": reminders_sent,
    }


# ---------------------------------------------------------------------------
# List trainings
# ---------------------------------------------------------------------------

def list_trainings(status: str | None = None, area_code: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List trainings with optional filters and progress info."""
    conditions = []
    params: list[Any] = []

    if status:
        conditions.append("t.status = %s")
        params.append(status)
    if area_code:
        conditions.append("a.code = %s")
        params.append(area_code)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT t.id, t.title, t.training_type, t.deadline, t.status,
                       a.code AS area_code, a.name_pl AS area_name,
                       COUNT(tr.id) AS total_records,
                       COUNT(tr.id) FILTER (WHERE tr.status = 'completed') AS completed_count,
                       t.created_at
                FROM compliance_trainings t
                JOIN compliance_areas a ON a.id = t.area_id
                LEFT JOIN compliance_training_records tr ON tr.training_id = t.id
                {where}
                GROUP BY t.id, a.code, a.name_pl
                ORDER BY t.created_at DESC
                LIMIT %s
            """, params)
            rows = cur.fetchall()

    return [
        {
            "training_id": r[0],
            "title": r[1],
            "training_type": r[2],
            "deadline": str(r[3]) if r[3] else None,
            "status": r[4],
            "area_code": r[5],
            "area_name": r[6],
            "total_assigned": r[7],
            "completed": r[8],
            "progress_pct": round(r[8] / r[7] * 100, 1) if r[7] > 0 else 0,
            "created_at": r[9].isoformat() if r[9] else None,
        }
        for r in rows
    ]
