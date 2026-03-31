"""GDPR compliance: access requests, data correction, anonymization."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from .audit_logger import log_action

log = structlog.get_logger("employee_evaluator.gdpr")


def handle_access_request(
    person_id: UUID,
    conn: psycopg.Connection,
    requested_by: str = "data_subject",
) -> dict[str, Any]:
    """Handle GDPR Article 15 access request.

    Returns a summary of all collected evaluation data for the person.
    """
    log_action(
        action="gdpr_access_request",
        person_id=person_id,
        details={"requested_by": requested_by},
        performed_by=requested_by,
        conn=conn,
    )

    result: dict[str, Any] = {
        "person_id": str(person_id),
        "request_type": "access",
        "data_categories": [],
    }

    # ── Signals ──────────────────────────────────────────────────────
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT COUNT(*) as count,
                      MIN(week_start) as earliest,
                      MAX(week_start) as latest
               FROM employee_signals
               WHERE person_id = %s""",
            (str(person_id),),
        )
        signals_info = cur.fetchone()

    if signals_info and signals_info["count"] > 0:
        result["data_categories"].append("employee_signals")
        result["signals"] = {
            "weeks_collected": signals_info["count"],
            "period": f"{signals_info['earliest']} to {signals_info['latest']}",
            "data_types": [
                "teams_messages", "emails", "commits",
                "tasks", "documents", "hr_data",
            ],
        }

    # ── Competency scores ────────────────────────────────────────────
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT cycle_id, overall_score, overall_label,
                      data_completeness, scored_at
               FROM employee_competency_scores
               WHERE person_id = %s
               ORDER BY scored_at DESC""",
            (str(person_id),),
        )
        scores = cur.fetchall()

    if scores:
        result["data_categories"].append("competency_scores")
        result["competency_scores"] = [
            {
                "cycle_id": str(s["cycle_id"]),
                "overall_score": s["overall_score"],
                "overall_label": s["overall_label"],
                "data_completeness": s["data_completeness"],
                "scored_at": str(s["scored_at"]),
            }
            for s in scores
        ]

    # ── Reports ──────────────────────────────────────────────────────
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT cycle_id, report_type, executive_summary,
                      nine_box_label, gdpr_basis, retention_until,
                      generated_at
               FROM employee_reports
               WHERE person_id = %s
               ORDER BY generated_at DESC""",
            (str(person_id),),
        )
        reports = cur.fetchall()

    if reports:
        result["data_categories"].append("evaluation_reports")
        result["reports"] = [
            {
                "cycle_id": str(r["cycle_id"]),
                "report_type": r["report_type"],
                "executive_summary": r["executive_summary"],
                "nine_box_label": r["nine_box_label"],
                "gdpr_basis": r["gdpr_basis"],
                "retention_until": str(r["retention_until"]),
                "generated_at": str(r["generated_at"]),
            }
            for r in reports
        ]

    # ── Audit log ────────────────────────────────────────────────────
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT action, performed_by, logged_at
               FROM evaluation_audit_log
               WHERE person_id = %s
               ORDER BY logged_at DESC
               LIMIT 50""",
            (str(person_id),),
        )
        audit = cur.fetchall()

    if audit:
        result["data_categories"].append("audit_log")
        result["audit_entries"] = len(audit)

    result["legal_basis"] = "legitimate_interest"
    result["retention_policy"] = "Reports retained for 2 years from generation."

    log.info(
        "gdpr_access_fulfilled",
        person_id=str(person_id),
        categories=result["data_categories"],
    )
    return result


def anonymize_employee_data(
    person_id: UUID,
    conn: psycopg.Connection,
    performed_by: str = "system",
) -> dict[str, Any]:
    """Anonymize all evaluation data for a person (GDPR Article 17).

    Performs soft-delete: nullifies personal data but retains anonymized
    aggregate records for statistical purposes. Respects retention_until dates.
    """
    log_action(
        action="gdpr_anonymization_requested",
        person_id=person_id,
        details={"performed_by": performed_by},
        performed_by=performed_by,
        conn=conn,
    )

    today = date.today()
    result: dict[str, Any] = {"person_id": str(person_id), "anonymized": {}}

    # ── Delete signals ───────────────────────────────────────────────
    with conn.cursor() as cur:
        cur.execute(
            """DELETE FROM employee_signals WHERE person_id = %s""",
            (str(person_id),),
        )
        result["anonymized"]["signals_deleted"] = cur.rowcount

    # ── Anonymize competency scores ──────────────────────────────────
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE employee_competency_scores
               SET delivery_evidence = NULL,
                   collaboration_evidence = NULL,
                   communication_evidence = NULL,
                   initiative_evidence = NULL,
                   knowledge_evidence = NULL,
                   leadership_evidence = NULL,
                   growth_evidence = NULL,
                   relationships_evidence = NULL
               WHERE person_id = %s""",
            (str(person_id),),
        )
        result["anonymized"]["scores_anonymized"] = cur.rowcount

    # ── Delete reports past retention (or all if requested) ──────────
    with conn.cursor() as cur:
        cur.execute(
            """DELETE FROM employee_reports
               WHERE person_id = %s
                 AND retention_until <= %s""",
            (str(person_id), today),
        )
        expired_count = cur.rowcount

        # For reports still within retention, nullify personal narratives
        cur.execute(
            """UPDATE employee_reports
               SET executive_summary = '[ANONYMIZED]',
                   narrative_strengths = '[ANONYMIZED]',
                   narrative_development = '[ANONYMIZED]',
                   key_strengths = '[]'::jsonb,
                   development_areas = '[]'::jsonb,
                   suggested_actions = '[]'::jsonb
               WHERE person_id = %s
                 AND retention_until > %s""",
            (str(person_id), today),
        )
        result["anonymized"]["reports_deleted"] = expired_count
        result["anonymized"]["reports_anonymized"] = cur.rowcount

    log_action(
        action="gdpr_anonymization_completed",
        person_id=person_id,
        details=result["anonymized"],
        performed_by=performed_by,
        conn=conn,
    )

    log.info(
        "employee_data_anonymized",
        person_id=str(person_id),
        **result["anonymized"],
    )
    return result
