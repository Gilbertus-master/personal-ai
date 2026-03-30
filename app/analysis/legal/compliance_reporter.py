"""
Compliance Reporter — raporty, dashboard data, daily/weekly updates.

Raporty:
- Daily update: krótki status na WhatsApp (overdue, upcoming, open matters)
- Weekly report: pełny przegląd compliance per area
- Area report: szczegółowy raport dla konkretnego obszaru
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import os
import subprocess
from datetime import datetime, timezone
from typing import Any

from app.db.postgres import get_pg_connection
from dotenv import load_dotenv

load_dotenv()

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "")


def generate_daily_update() -> str | None:
    """Generuje dzienny update compliance na WhatsApp.

    Zwraca None jeśli nie ma nic do raportowania.
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Overdue deadlines
            cur.execute("""
                SELECT COUNT(*) FROM compliance_deadlines
                WHERE status = 'overdue'
                   OR (deadline_date < CURRENT_DATE AND status = 'pending')
            """)
            overdue_count = cur.fetchall()[0][0]

            # Upcoming deadlines (7 days)
            cur.execute("""
                SELECT COUNT(*) FROM compliance_deadlines
                WHERE deadline_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
                  AND status IN ('pending', 'in_progress')
            """)
            upcoming_count = cur.fetchall()[0][0]

            # Open matters by priority
            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE priority = 'critical') AS critical
                FROM compliance_matters
                WHERE status NOT IN ('completed', 'closed', 'cancelled')
            """)
            matters_row = cur.fetchone()
            open_matters = matters_row[0]
            critical_matters = matters_row[1]

            # Stale documents
            cur.execute("""
                SELECT COUNT(*) FROM compliance_documents
                WHERE status = 'active' AND review_due <= CURRENT_DATE
            """)
            stale_docs = cur.fetchall()[0][0]

            # Pending trainings
            cur.execute("""
                SELECT COUNT(*) FROM compliance_trainings
                WHERE status IN ('active', 'overdue')
            """)
            pending_trainings = cur.fetchall()[0][0]

            # Pending signatures
            cur.execute("""
                SELECT COUNT(*) FROM compliance_documents
                WHERE signature_status = 'pending'
                  AND status IN ('approved', 'active')
            """)
            pending_signatures = cur.fetchall()[0][0]

    # Nothing to report?
    if (overdue_count == 0 and upcoming_count == 0 and open_matters == 0
            and stale_docs == 0 and pending_trainings == 0 and pending_signatures == 0):
        return None

    msg = (
        "\U0001f4cb *Compliance Daily*\n"
        f"\u26a0\ufe0f Overdue: {overdue_count} termin\u00f3w\n"
        f"\U0001f4c5 Nadchodz\u0105ce (7d): {upcoming_count}\n"
        f"\U0001f4c2 Otwarte sprawy: {open_matters} (critical: {critical_matters})\n"
        f"\U0001f4c4 Dokumenty do przegl\u0105du: {stale_docs}\n"
        f"\U0001f4da Szkolenia w toku: {pending_trainings}\n"
        f"\u270d\ufe0f Podpisy oczekuj\u0105ce: {pending_signatures}\n"
        "\nSzczeg\u00f3\u0142y: /compliance/dashboard"
    )

    log.info("daily_update_generated",
             overdue=overdue_count, upcoming=upcoming_count, open=open_matters)
    return msg


def generate_weekly_report() -> dict[str, Any]:
    """Tygodniowy raport compliance per area. Wysyła podsumowanie na WhatsApp."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Per-area stats
            cur.execute("""
                SELECT a.code, a.name_pl,
                    (SELECT COUNT(*) FROM compliance_obligations o
                     WHERE o.area_id = a.id AND o.compliance_status = 'compliant') AS compliant,
                    (SELECT COUNT(*) FROM compliance_obligations o
                     WHERE o.area_id = a.id AND o.compliance_status = 'partially_compliant') AS partial,
                    (SELECT COUNT(*) FROM compliance_obligations o
                     WHERE o.area_id = a.id AND o.compliance_status = 'non_compliant') AS non_compliant,
                    (SELECT COUNT(*) FROM compliance_matters m
                     WHERE m.area_id = a.id AND m.created_at > CURRENT_DATE - 7
                       AND m.status NOT IN ('completed','closed','cancelled')) AS opened_week,
                    (SELECT COUNT(*) FROM compliance_matters m
                     WHERE m.area_id = a.id AND m.status IN ('completed','closed')
                       AND m.updated_at > CURRENT_DATE - 7) AS closed_week,
                    (SELECT COUNT(*) FROM compliance_deadlines d
                     WHERE d.area_id = a.id AND d.status = 'completed'
                       AND d.updated_at > CURRENT_DATE - 7) AS deadlines_met,
                    (SELECT COUNT(*) FROM compliance_deadlines d
                     WHERE d.area_id = a.id AND d.status = 'overdue') AS deadlines_missed,
                    (SELECT COUNT(*) FROM compliance_documents doc
                     WHERE doc.area_id = a.id AND doc.created_at > CURRENT_DATE - 7) AS docs_generated,
                    (SELECT COUNT(*) FROM compliance_documents doc
                     WHERE doc.area_id = a.id AND doc.status = 'approved'
                       AND doc.approved_at > CURRENT_DATE - 7) AS docs_approved,
                    (SELECT COUNT(*) FROM compliance_risk_assessments ra
                     WHERE ra.area_id = a.id AND ra.status = 'open') AS open_risks
                FROM compliance_areas a
                ORDER BY a.code
            """)
            rows = cur.fetchall()

    areas = []
    wa_lines = ["\U0001f4ca *Compliance Weekly*"]
    for r in rows:
        area = {
            "code": r[0], "name": r[1],
            "obligations": {"compliant": r[2], "partially_compliant": r[3], "non_compliant": r[4]},
            "matters": {"opened_this_week": r[5], "closed_this_week": r[6]},
            "deadlines": {"met_this_week": r[7], "missed": r[8]},
            "documents": {"generated": r[9], "approved": r[10]},
            "open_risks": r[11],
        }
        areas.append(area)
        # Only add to WhatsApp summary if there's activity
        if any([r[3], r[4], r[5], r[6], r[8], r[11]]):
            wa_lines.append(
                f"\n*{r[0]}* ({r[1]}): "
                f"obow. {r[2]}/{r[2]+r[3]+r[4]}, "
                f"sprawy +{r[5]}/-{r[6]}, "
                f"ryzyka {r[11]}"
            )

    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "areas": areas}

    # Send WhatsApp summary (max 1500 chars)
    wa_msg = "\n".join(wa_lines)[:1500]
    if WA_TARGET and len(wa_lines) > 1:
        try:
            subprocess.run(
                [OPENCLAW_BIN, "message", "send", "--channel", "whatsapp",
                 "--target", WA_TARGET, "--message", wa_msg],
                capture_output=True, text=True, timeout=30,
            )
            report["whatsapp_sent"] = True
        except Exception as exc:
            log.warning("weekly_wa_send_failed", error=str(exc))
            report["whatsapp_sent"] = False

    log.info("weekly_report_generated", areas=len(areas))
    return report


def generate_area_report(area_code: str) -> dict[str, Any]:
    """Szczegółowy raport dla obszaru compliance."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Area detail
            cur.execute("""
                SELECT id, code, name_pl, name_en, governing_body, key_regulations,
                       risk_level, last_reviewed
                FROM compliance_areas WHERE code = %s
            """, (area_code.upper(),))
            area_row = cur.fetchone()
            if not area_row:
                return {"error": "area_not_found", "code": area_code}

            area_id = area_row[0]
            area = {
                "code": area_row[1], "name_pl": area_row[2], "name_en": area_row[3],
                "governing_body": area_row[4], "key_regulations": area_row[5],
                "risk_level": area_row[6],
                "last_reviewed": str(area_row[7]) if area_row[7] else None,
            }

            # Obligations
            cur.execute("""
                SELECT id, title, obligation_type, compliance_status, next_deadline,
                       penalty_description
                FROM compliance_obligations
                WHERE area_id = %s ORDER BY next_deadline ASC NULLS LAST
            """, (area_id,))
            obligations = [
                {"id": r[0], "title": r[1], "type": r[2], "status": r[3],
                 "next_deadline": str(r[4]) if r[4] else None, "penalty": r[5]}
                for r in cur.fetchall()
            ]

            # Open matters
            cur.execute("""
                SELECT id, title, matter_type, priority, phase, status, created_at
                FROM compliance_matters
                WHERE area_id = %s AND status NOT IN ('completed','closed','cancelled')
                ORDER BY priority DESC, created_at DESC
            """, (area_id,))
            matters = [
                {"id": r[0], "title": r[1], "type": r[2], "priority": r[3],
                 "phase": r[4], "status": r[5], "created_at": str(r[6])}
                for r in cur.fetchall()
            ]

            # Active documents
            cur.execute("""
                SELECT id, title, doc_type, status, version, valid_until, review_due
                FROM compliance_documents
                WHERE area_id = %s AND status IN ('active','approved','draft')
                ORDER BY created_at DESC
            """, (area_id,))
            documents = [
                {"id": r[0], "title": r[1], "type": r[2], "status": r[3],
                 "version": r[4], "valid_until": str(r[5]) if r[5] else None,
                 "review_due": str(r[6]) if r[6] else None}
                for r in cur.fetchall()
            ]

            # Upcoming deadlines
            cur.execute("""
                SELECT id, title, deadline_date, deadline_type, status
                FROM compliance_deadlines
                WHERE area_id = %s AND status IN ('pending','in_progress','overdue')
                ORDER BY deadline_date ASC
            """, (area_id,))
            deadlines = [
                {"id": r[0], "title": r[1], "date": str(r[2]), "type": r[3], "status": r[4]}
                for r in cur.fetchall()
            ]

            # Active trainings
            cur.execute("""
                SELECT id, title, training_type, status, deadline
                FROM compliance_trainings
                WHERE area_id = %s AND status NOT IN ('completed','cancelled')
                ORDER BY deadline ASC NULLS LAST
            """, (area_id,))
            trainings = [
                {"id": r[0], "title": r[1], "type": r[2], "status": r[3],
                 "deadline": str(r[4]) if r[4] else None}
                for r in cur.fetchall()
            ]

            # Risk assessments
            cur.execute("""
                SELECT id, risk_title, likelihood, impact, risk_score, status
                FROM compliance_risk_assessments
                WHERE area_id = %s AND status IN ('open','accepted')
                ORDER BY risk_score DESC NULLS LAST
            """, (area_id,))
            risks = [
                {"id": r[0], "title": r[1], "likelihood": r[2], "impact": r[3],
                 "score": float(r[4]) if r[4] else None, "status": r[5]}
                for r in cur.fetchall()
            ]

            # RACI matrix
            cur.execute("""
                SELECT r.person_id, p.full_name, r.role, r.notes
                FROM compliance_raci r
                LEFT JOIN people p ON p.id = r.person_id
                WHERE r.area_id = %s
                ORDER BY r.role, p.full_name
            """, (area_id,))
            raci = [
                {"person_id": r[0], "person_name": r[1], "role": r[2], "notes": r[3]}
                for r in cur.fetchall()
            ]

    log.info("area_report_generated", area_code=area_code)
    return {
        "area": area,
        "obligations": obligations,
        "open_matters": matters,
        "documents": documents,
        "upcoming_deadlines": deadlines,
        "trainings": trainings,
        "risks": risks,
        "raci": raci,
    }
