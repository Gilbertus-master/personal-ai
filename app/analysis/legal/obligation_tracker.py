"""
Obligation Tracker — monitoring obowiązków prawnych, terminów i przypomnień.

Funkcje:
- CRUD obowiązków (create, update, list, get)
- Automatyczne obliczanie next_deadline na podstawie recurrence
- System przypomnień (30/14/7/3/1 dni przed terminem) via WhatsApp
- Auto-update compliance_status na podstawie fulfillment
- Oznaczanie overdue gdy termin minął
- Tworzenie compliance_deadlines z obligations

Cron: codziennie 6:15 (w ramach legal_compliance_daily.sh)
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import os
import subprocess
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.db.postgres import get_pg_connection
from dotenv import load_dotenv

load_dotenv()

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _calculate_next_deadline(current_deadline: date, frequency: str) -> date | None:
    """Oblicza następny termin na podstawie frequency.
    monthly → +1 month, quarterly → +3 months, semi_annual → +6, annual → +12, biennial → +24.
    Zwraca None dla one_time, on_change, on_demand.
    """
    freq_months = {
        "monthly": 1,
        "quarterly": 3,
        "semi_annual": 6,
        "annual": 12,
        "biennial": 24,
    }
    months = freq_months.get(frequency)
    if months is None:
        return None

    year = current_deadline.year
    month = current_deadline.month + months
    while month > 12:
        month -= 12
        year += 1
    day = min(current_deadline.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    """Return number of days in a given month."""
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def _create_deadline_from_obligation(
    obligation_id: int,
    obligation_title: str,
    deadline_date: date,
    area_id: int,
    responsible_person_id: int | None = None,
) -> int:
    """Tworzy wpis w compliance_deadlines. Zwraca deadline_id."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO compliance_deadlines
                    (title, deadline_date, deadline_type, area_id, obligation_id,
                     responsible_person_id, status)
                VALUES (%s, %s, 'filing', %s, %s, %s, 'pending')
                RETURNING id
                """,
                (obligation_title, deadline_date, area_id, obligation_id,
                 responsible_person_id),
            )
            deadline_id = cur.fetchall()[0][0]
        conn.commit()
    log.info("compliance_deadline_created",
             deadline_id=deadline_id, obligation_id=obligation_id,
             deadline_date=str(deadline_date))
    return deadline_id


def _send_reminder_wa(message: str) -> None:
    """Wysyła WhatsApp reminder via openclaw. Timeout 30s."""
    if not WA_TARGET:
        log.warning("wa_reminder_skipped", reason="WA_TARGET not set")
        return
    try:
        subprocess.run(
            [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
             "--target", WA_TARGET, "--message", message],
            capture_output=True, text=True, timeout=30,
        )
        log.info("wa_reminder_sent", target=WA_TARGET)
    except Exception as e:
        log.error("wa_reminder_failed", error=str(e))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def create_obligation(
    area_code: str,
    title: str,
    obligation_type: str,
    description: str | None = None,
    legal_basis: str | None = None,
    frequency: str | None = None,
    deadline_rule: str | None = None,
    next_deadline: str | None = None,
    penalty_description: str | None = None,
    penalty_max_pln: float | None = None,
    applies_to: list[str] | None = None,
    responsible_role: str | None = None,
    required_documents: list[str] | None = None,
) -> dict[str, Any]:
    """Tworzy nowy obowiązek prawny. Automatycznie tworzy deadline jeśli next_deadline podany."""
    deadline_date = None
    if next_deadline:
        deadline_date = date.fromisoformat(next_deadline)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM compliance_areas WHERE code = %s",
                        (area_code.upper(),))
            row = cur.fetchone()
            if not row:
                return {"error": "area_not_found", "code": area_code}
            area_id = row[0]

            cur.execute(
                """
                INSERT INTO compliance_obligations
                    (area_id, title, description, legal_basis, obligation_type,
                     frequency, deadline_rule, next_deadline,
                     penalty_description, penalty_max_pln,
                     applies_to, responsible_role, required_documents,
                     status, compliance_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        'active', 'unknown')
                RETURNING id
                """,
                (area_id, title, description, legal_basis, obligation_type,
                 frequency, deadline_rule, deadline_date,
                 penalty_description, penalty_max_pln,
                 applies_to or [], responsible_role, required_documents or []),
            )
            obligation_id = cur.fetchall()[0][0]
        conn.commit()

    log.info("compliance_obligation_created",
             obligation_id=obligation_id, title=title, area_code=area_code)

    if deadline_date:
        _create_deadline_from_obligation(
            obligation_id=obligation_id,
            obligation_title=title,
            deadline_date=deadline_date,
            area_id=area_id,
        )

    return {
        "id": obligation_id,
        "title": title,
        "area_code": area_code.upper(),
        "next_deadline": str(deadline_date) if deadline_date else None,
        "status": "active",
        "compliance_status": "unknown",
    }


def list_obligations(
    area_code: str | None = None,
    compliance_status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Lista obowiązków z filtrami. JOIN z compliance_areas na code."""
    conditions: list[str] = []
    params: list[Any] = []

    if area_code:
        conditions.append("ca.code = %s")
        params.append(area_code.upper())
    if compliance_status:
        conditions.append("co.compliance_status = %s")
        params.append(compliance_status)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT co.id, co.title, co.obligation_type, co.frequency,
                       co.next_deadline, co.compliance_status, co.status,
                       co.penalty_description, co.penalty_max_pln,
                       co.applies_to, co.responsible_role,
                       ca.code as area_code, ca.name_pl as area_name,
                       co.last_fulfilled_at
                FROM compliance_obligations co
                JOIN compliance_areas ca ON ca.id = co.area_id
                {where}
                ORDER BY co.next_deadline ASC NULLS LAST
                LIMIT %s
            """, params)
            return [
                {
                    "id": r[0], "title": r[1], "obligation_type": r[2],
                    "frequency": r[3],
                    "next_deadline": str(r[4]) if r[4] else None,
                    "compliance_status": r[5], "status": r[6],
                    "penalty_description": r[7],
                    "penalty_max_pln": float(r[8]) if r[8] else None,
                    "applies_to": r[9], "responsible_role": r[10],
                    "area_code": r[11], "area_name": r[12],
                    "last_fulfilled_at": str(r[13]) if r[13] else None,
                }
                for r in cur.fetchall()
            ]


def get_overdue_obligations() -> list[dict[str, Any]]:
    """Zwraca obowiązki z next_deadline < TODAY i compliance_status != 'compliant'."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT co.id, co.title, co.obligation_type, co.frequency,
                       co.next_deadline, co.compliance_status, co.status,
                       co.penalty_description, co.penalty_max_pln,
                       ca.code as area_code, ca.name_pl as area_name,
                       CURRENT_DATE - co.next_deadline as days_overdue
                FROM compliance_obligations co
                JOIN compliance_areas ca ON ca.id = co.area_id
                WHERE co.next_deadline < CURRENT_DATE
                  AND co.compliance_status != 'compliant'
                  AND co.status = 'active'
                ORDER BY co.next_deadline ASC
            """)
            return [
                {
                    "id": r[0], "title": r[1], "obligation_type": r[2],
                    "frequency": r[3], "next_deadline": str(r[4]),
                    "compliance_status": r[5], "status": r[6],
                    "penalty_description": r[7],
                    "penalty_max_pln": float(r[8]) if r[8] else None,
                    "area_code": r[9], "area_name": r[10],
                    "days_overdue": r[11],
                }
                for r in cur.fetchall()
            ]


def fulfill_obligation(
    obligation_id: int,
    evidence_description: str | None = None,
) -> dict[str, Any]:
    """Oznacza obowiązek jako spełniony. Aktualizuje last_fulfilled_at, compliance_status='compliant'.
    Jeśli recurrence != 'one_time' → oblicz i ustaw nowy next_deadline.
    Opcjonalnie tworzy compliance_audit_evidence.
    """
    now = datetime.now(timezone.utc)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, frequency, next_deadline, area_id
                FROM compliance_obligations WHERE id = %s
            """, (obligation_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "obligation_not_found", "id": obligation_id}

            ob_id, ob_title, frequency, current_deadline, area_id = row

            # Calculate new deadline for recurring obligations
            new_deadline = None
            if frequency and frequency not in ("one_time", "on_change", "on_demand") and current_deadline:
                new_deadline = _calculate_next_deadline(current_deadline, frequency)

            # Update obligation
            cur.execute("""
                UPDATE compliance_obligations
                SET compliance_status = 'compliant',
                    last_fulfilled_at = %s,
                    next_deadline = COALESCE(%s, next_deadline),
                    updated_at = %s
                WHERE id = %s
            """, (now, new_deadline, now, ob_id))

            # Mark current deadline(s) as completed
            cur.execute("""
                UPDATE compliance_deadlines
                SET status = 'completed', completed_at = %s
                WHERE obligation_id = %s AND status IN ('pending', 'in_progress', 'overdue')
            """, (now, ob_id))

            # Create new deadline if recurring
            if new_deadline:
                cur.execute("""
                    INSERT INTO compliance_deadlines
                        (title, deadline_date, deadline_type, area_id, obligation_id, status)
                    VALUES (%s, %s, 'filing', %s, %s, 'pending')
                """, (ob_title, new_deadline, area_id, ob_id))

            # Create audit evidence if description provided
            evidence_id = None
            if evidence_description:
                cur.execute("""
                    INSERT INTO compliance_audit_evidence
                        (obligation_id, evidence_type, title, description, verified_at)
                    VALUES (%s, 'document', %s, %s, %s)
                    RETURNING id
                """, (ob_id, f"Fulfillment: {ob_title}", evidence_description, now))
                evidence_id = cur.fetchall()[0][0]

        conn.commit()

    log.info("compliance_obligation_fulfilled",
             obligation_id=ob_id, new_deadline=str(new_deadline) if new_deadline else None)

    return {
        "id": ob_id,
        "title": ob_title,
        "compliance_status": "compliant",
        "fulfilled_at": str(now),
        "new_deadline": str(new_deadline) if new_deadline else None,
        "evidence_id": evidence_id,
    }


# ---------------------------------------------------------------------------
# Deadline monitor (cron)
# ---------------------------------------------------------------------------

def check_deadlines_and_remind() -> dict[str, Any]:
    """Główna funkcja cron. Sprawdza compliance_deadlines:
    1. Oznacz overdue (deadline_date < TODAY i status='pending')
    2. Dla każdego pending deadline sprawdź reminder_days array
    3. Jeśli TODAY jest w reminder_days od deadline → wyślij WhatsApp
    4. Aktualizuj last_reminder_sent
    """
    today = date.today()
    checked = 0
    reminded = 0
    overdue_marked = 0

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # 1. Mark overdue
            cur.execute("""
                UPDATE compliance_deadlines
                SET status = 'overdue'
                WHERE deadline_date < %s AND status = 'pending'
                RETURNING id
            """, (today,))
            overdue_marked = len(cur.fetchall())

            # 2-3. Check pending/in_progress deadlines for reminders
            cur.execute("""
                SELECT d.id, d.title, d.deadline_date, d.reminder_days,
                       d.last_reminder_sent, a.code as area_code, a.name_pl as area_name
                FROM compliance_deadlines d
                LEFT JOIN compliance_areas a ON a.id = d.area_id
                WHERE d.status IN ('pending', 'in_progress')
                  AND d.deadline_date >= %s
                ORDER BY d.deadline_date ASC
            """, (today,))
            rows = cur.fetchall()
            checked = len(rows)

            for row in rows:
                dl_id, dl_title, dl_date, reminder_days, last_sent, area_code, area_name = row
                days_until = (dl_date - today).days

                if reminder_days and days_until in reminder_days:
                    # Skip if already reminded today
                    if last_sent and last_sent >= today:
                        continue

                    message = (
                        f"\u26a0\ufe0f *Compliance Deadline*\n"
                        f"{dl_title}\n"
                        f"Termin: {dl_date} ({days_until} dni)\n"
                        f"Obszar: {area_name or area_code or 'N/A'}\n"
                    )
                    _send_reminder_wa(message)

                    cur.execute("""
                        UPDATE compliance_deadlines
                        SET last_reminder_sent = %s
                        WHERE id = %s
                    """, (today, dl_id))
                    reminded += 1

        conn.commit()

    log.info("deadline_check_completed",
             checked=checked, reminded=reminded, overdue_marked=overdue_marked)

    return {"checked": checked, "reminded": reminded, "overdue_marked": overdue_marked}


def run_deadline_monitor() -> dict[str, Any]:
    """Entry point dla cron. Wywołuje check_deadlines_and_remind().
    Dodatkowo: update compliance_status na 'non_compliant' dla overdue obligations.
    """
    result = check_deadlines_and_remind()

    # Update compliance_status for obligations with overdue deadlines
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE compliance_obligations co
                SET compliance_status = 'non_compliant', updated_at = NOW()
                FROM compliance_deadlines cd
                WHERE cd.obligation_id = co.id
                  AND cd.status = 'overdue'
                  AND co.compliance_status != 'non_compliant'
                RETURNING co.id
            """)
            updated = len(cur.fetchall())
        conn.commit()

    if updated:
        log.warning("obligations_marked_non_compliant", count=updated)
    result["obligations_marked_non_compliant"] = updated

    return result
