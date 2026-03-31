"""Audit logging for all evaluation-related actions."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
import structlog

log = structlog.get_logger("employee_evaluator.audit")


def log_action(
    action: str,
    person_id: UUID | None,
    details: dict[str, Any] | None,
    performed_by: str,
    conn: psycopg.Connection,
) -> None:
    """Insert an entry into evaluation_audit_log.

    Args:
        action: Action type (e.g., 'evaluation_started', 'data_accessed',
                'report_generated', 'gdpr_access_request', 'data_anonymized').
        person_id: Target person (None for system-wide actions).
        details: Additional context as JSON.
        performed_by: Who performed the action (user ID or 'system').
        conn: Database connection.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO evaluation_audit_log
                   (person_id, action, performed_by, details)
                   VALUES (%s, %s, %s, %s)""",
                (
                    str(person_id) if person_id else None,
                    action,
                    performed_by,
                    json.dumps(details, default=str, ensure_ascii=False) if details else None,
                ),
            )
        log.debug("audit_logged", action=action, person_id=str(person_id) if person_id else None)
    except Exception as e:
        # Audit logging should never break the caller
        log.error(
            "audit_log_failed",
            action=action,
            person_id=str(person_id) if person_id else None,
            error=str(e),
        )
