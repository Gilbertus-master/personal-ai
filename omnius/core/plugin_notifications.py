"""Plugin review notifications — creates operator tasks for Gilbertus to pick up.

Direct WhatsApp notification requires Gilbertus alert_manager which is not
accessible from Omnius. Instead, creates an omnius_operator_tasks entry that
Gilbertus monitors and surfaces to Sebastian.
"""
from __future__ import annotations

import structlog

from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)


async def notify_plugin_ready_for_review(
    plugin_name: str,
    proposed_by: str,
    review_score: float,
    tenant: str,
) -> None:
    """Create an operator task notifying that a plugin passed review.

    Gilbertus polls omnius_operator_tasks and will surface this to Sebastian
    via WhatsApp or morning brief.
    """
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO omnius_operator_tasks (title, description, source, status)
                    VALUES (%s, %s, 'plugin_review', 'pending')
                """, (
                    f"Plugin review: {plugin_name}",
                    f"Plugin '{plugin_name}' proposed by {proposed_by} in tenant {tenant} "
                    f"passed automated review (score: {review_score:.2f}). "
                    f"Awaiting Sebastian's approval.",
                ))
            conn.commit()
        log.info("plugin_review_notification_created",
                 plugin_name=plugin_name, tenant=tenant)
    except Exception as e:
        log.error("plugin_review_notification_failed",
                  plugin_name=plugin_name, error=str(e))
