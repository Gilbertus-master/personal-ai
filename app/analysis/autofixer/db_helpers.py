"""
Shared database helpers for code fixers.

Consolidates common operations like marking findings as resolved/attempted.
"""
from __future__ import annotations

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)


def mark_resolved(finding_ids: list[int]) -> None:
    """Mark multiple findings as resolved."""
    if not finding_ids:
        return
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                placeholders = ",".join(["%s"] * len(finding_ids))
                cur.execute(f"""
                    UPDATE code_review_findings
                    SET resolved = TRUE, resolved_at = NOW()
                    WHERE id IN ({placeholders})
                """, tuple(finding_ids))
                rowcount = cur.rowcount
            conn.commit()
            log.info("autofixer.mark_resolved", count=len(finding_ids), ids=finding_ids, rowcount=rowcount)
    except Exception:
        log.exception("autofixer.db_helpers.mark_resolved_failed", ids=finding_ids)
        raise


def mark_attempted(finding_ids: list[int]) -> None:
    """Increment attempt counter for findings and flag manual review if exhausted."""
    if not finding_ids:
        return
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                placeholders = ",".join(["%s"] * len(finding_ids))
                cur.execute(f"""
                    UPDATE code_review_findings
                    SET fix_attempted_at = NOW(),
                        fix_attempt_count = fix_attempt_count + 1,
                        manual_review = CASE WHEN fix_attempt_count + 1 >= 6 THEN TRUE ELSE manual_review END
                    WHERE id IN ({placeholders})
                """, tuple(finding_ids))
                rowcount = cur.rowcount
            conn.commit()
            log.info("autofixer.mark_attempted", count=len(finding_ids), rowcount=rowcount)
    except Exception:
        log.exception("autofixer.db_helpers.mark_attempted_failed", ids=finding_ids)
        raise
