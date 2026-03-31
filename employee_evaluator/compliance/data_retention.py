"""Data retention enforcement: delete expired evaluation reports."""

from __future__ import annotations

from datetime import date

import psycopg
import structlog

from .audit_logger import log_action

log = structlog.get_logger("employee_evaluator.retention")


def cleanup_expired_data(conn: psycopg.Connection) -> int:
    """Delete reports and scores that have passed their retention_until date.

    Returns:
        Number of expired reports deleted.
    """
    today = date.today()
    deleted_total = 0

    # ── Expired reports ──────────────────────────────────────────────
    with conn.cursor() as cur:
        cur.execute(
            """DELETE FROM employee_reports
               WHERE retention_until < %s
               RETURNING person_id, cycle_id, report_type""",
            (today,),
        )
        deleted_reports = cur.fetchall()
        deleted_total = len(deleted_reports)

    if deleted_total > 0:
        log_action(
            action="retention_cleanup",
            person_id=None,
            details={
                "reports_deleted": deleted_total,
                "cutoff_date": today.isoformat(),
            },
            performed_by="system",
            conn=conn,
        )

    log.info(
        "retention_cleanup_completed",
        reports_deleted=deleted_total,
        cutoff_date=today.isoformat(),
    )
    return deleted_total
