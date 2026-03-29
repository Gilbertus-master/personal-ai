"""
Alert Manager — three-tier escalation with dedup, snooze, and acknowledgment.

Tier 1 (AUTO): System naprawil problem samodzielnie. Log only.
  Examples: token refreshed, worker restarted, retry succeeded, DLQ item resolved

Tier 2 (INFO): Problem wykryty, moze sie sam naprawic. WhatsApp info 1x.
  Examples: source 50% SLA, circuit breaker opened, budget at 80%, backlog growing

Tier 3 (CRITICAL): Wymaga ludzkiej akcji. WhatsApp co 2h az acknowledge.
  Examples: source > 100% SLA, token expired (can't auto-refresh), disk > 90%,
            DLQ items abandoned, Graph API auth requires re-login
"""
from __future__ import annotations

import os
import subprocess

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger("alert_manager")

OPENCLAW_BIN = os.getenv("OPENCLAW_BIN", "openclaw")
WA_TARGET = os.getenv("WA_TARGET", "+48505441635")

# Rate limit: max WhatsApp messages per hour
MAX_WA_PER_HOUR = 5


class AlertManager:
    """Three-tier alert escalation with dedup and WhatsApp delivery."""

    def __init__(self):
        self.dedup_window = 4 * 3600  # 4 hours — same category+title not re-alerted
        self.critical_repeat = 2 * 3600  # repeat every 2h until ack

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        tier: int,
        category: str,
        title: str,
        message: str,
        fix_command: str | None = None,
        auto_fix_attempted: bool = False,
        auto_fix_result: str | None = None,
    ) -> int | None:
        """Send alert with dedup and escalation. Returns alert id or None if deduped."""
        if tier not in (1, 2, 3):
            raise ValueError(f"Invalid tier: {tier}. Must be 1, 2, or 3.")

        # Dedup check
        if self._is_duplicate(category, title):
            log.info("alert_deduped", tier=tier, category=category, title=title)
            return None

        # Insert alert
        alert_id = self._insert_alert(
            tier=tier,
            category=category,
            title=title,
            message=message,
            fix_command=fix_command,
            auto_fix_attempted=auto_fix_attempted,
            auto_fix_result=auto_fix_result,
        )

        # Deliver based on tier
        if tier == 1:
            log.info(
                "alert_auto",
                alert_id=alert_id,
                category=category,
                title=title,
                fix_result=auto_fix_result,
            )
        elif tier == 2:
            self._deliver_whatsapp_info(alert_id, title, message)
        elif tier == 3:
            self._deliver_whatsapp_critical(alert_id, title, message, fix_command)

        return alert_id

    def acknowledge(self, alert_id: int, acknowledged_by: str = "sebastian") -> bool:
        """Human acknowledged alert — stop repeating. Returns True if found."""
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE guardian_alerts
                    SET acknowledged = TRUE,
                        acknowledged_at = NOW(),
                        acknowledged_by = %s
                    WHERE id = %s AND acknowledged = FALSE
                    RETURNING id
                    """,
                    (acknowledged_by, alert_id),
                )
                row = cur.fetchone()
            conn.commit()

        if row:
            log.info("alert_acknowledged", alert_id=alert_id, by=acknowledged_by)
            return True
        return False

    def acknowledge_latest(self, category: str | None = None) -> int:
        """Acknowledge all unacknowledged critical alerts. Returns count."""
        conditions = ["tier = 3", "acknowledged = FALSE"]
        params: list = []
        if category:
            conditions.append("category = %s")
            params.append(category)

        where = " AND ".join(conditions)

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE guardian_alerts
                    SET acknowledged = TRUE,
                        acknowledged_at = NOW(),
                        acknowledged_by = 'sebastian'
                    WHERE {where}
                    RETURNING id
                    """,
                    params,
                )
                rows = cur.fetchall()
            conn.commit()

        count = len(rows)
        if count:
            log.info("alerts_bulk_acknowledged", count=count, category=category)
        return count

    def repeat_unacknowledged(self) -> int:
        """Re-send WhatsApp for unacknowledged CRITICAL alerts older than repeat interval.
        Called by cron every 2h. Returns count of repeated alerts."""
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, title, message, fix_command, repeat_count
                    FROM guardian_alerts
                    WHERE tier = 3
                      AND acknowledged = FALSE
                      AND last_sent_at < NOW() - %s * INTERVAL '1 second'
                    ORDER BY created_at
                    """,
                    (self.critical_repeat,),
                )
                alerts = cur.fetchall()

        repeated = 0
        for alert_id, title, message, fix_command, repeat_count in alerts:
            if not self._can_send_whatsapp():
                log.warning("wa_rate_limit_hit", skipping_alert=alert_id)
                break

            repeat_num = repeat_count + 1
            wa_msg = (
                f"\U0001f534 Gilbertus CRITICAL (repeat #{repeat_num})\n"
                f"{title}\n"
                f"{message}"
            )
            if fix_command:
                wa_msg += f"\n\nFix: {fix_command}"
            wa_msg += '\n\nReply "ok" to acknowledge.'

            if self._send_whatsapp(wa_msg):
                with get_pg_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE guardian_alerts
                            SET repeat_count = %s,
                                last_sent_at = NOW()
                            WHERE id = %s
                            """,
                            (repeat_num, alert_id),
                        )
                    conn.commit()
                repeated += 1
                log.info("alert_repeated", alert_id=alert_id, repeat=repeat_num)

        return repeated

    def get_active(self, tier: int | None = None, limit: int = 20) -> list[dict]:
        """Get active (unacknowledged or recent) alerts."""
        conditions = []
        params: list = []
        if tier:
            conditions.append("tier = %s")
            params.append(tier)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, tier, category, title, message, fix_command,
                           auto_fix_attempted, auto_fix_result,
                           acknowledged, acknowledged_at::text, acknowledged_by,
                           repeat_count, last_sent_at::text, created_at::text
                    FROM guardian_alerts
                    {where}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (*params, limit),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_duplicate(self, category: str, title: str) -> bool:
        """Check if same category+title was alerted within dedup window."""
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM guardian_alerts
                    WHERE category = %s
                      AND title = %s
                      AND created_at > NOW() - %s * INTERVAL '1 second'
                    LIMIT 1
                    """,
                    (category, title, self.dedup_window),
                )
                return cur.fetchone() is not None

    def _insert_alert(
        self,
        tier: int,
        category: str,
        title: str,
        message: str,
        fix_command: str | None,
        auto_fix_attempted: bool,
        auto_fix_result: str | None,
    ) -> int:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO guardian_alerts
                        (tier, category, title, message, fix_command,
                         auto_fix_attempted, auto_fix_result)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (tier, category, title, message, fix_command,
                     auto_fix_attempted, auto_fix_result),
                )
                alert_id = cur.fetchone()[0]
            conn.commit()

        log.info(
            "alert_created",
            alert_id=alert_id,
            tier=tier,
            category=category,
            title=title,
        )
        return alert_id

    def _can_send_whatsapp(self) -> bool:
        """Rate limit: max MAX_WA_PER_HOUR WhatsApp messages per hour."""
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM guardian_alerts
                    WHERE tier IN (2, 3)
                      AND last_sent_at > NOW() - INTERVAL '1 hour'
                    """,
                )
                count = cur.fetchone()[0]
        return count < MAX_WA_PER_HOUR

    def _send_whatsapp(self, message: str) -> bool:
        """Send WhatsApp via openclaw. Returns True on success."""
        if not WA_TARGET:
            log.warning("wa_target_not_set")
            return False
        try:
            result = subprocess.run(
                [OPENCLAW_BIN, "message", "send",
                 "--channel", "whatsapp",
                 "--target", WA_TARGET,
                 "--message", message],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                log.error("wa_send_failed", stderr=result.stderr[:200])
                return False
            return True
        except Exception as exc:
            log.error("wa_send_error", error=str(exc))
            return False

    def _deliver_whatsapp_info(self, alert_id: int, title: str, message: str):
        """Tier 2: single info notification."""
        if not self._can_send_whatsapp():
            log.warning("wa_rate_limit_hit", alert_id=alert_id)
            return

        wa_msg = (
            f"\u2139\ufe0f Gilbertus Info\n"
            f"{title}\n"
            f"{message}"
        )
        self._send_whatsapp(wa_msg)

    def _deliver_whatsapp_critical(
        self, alert_id: int, title: str, message: str, fix_command: str | None
    ):
        """Tier 3: critical notification with fix command."""
        if not self._can_send_whatsapp():
            log.warning("wa_rate_limit_hit", alert_id=alert_id)
            return

        wa_msg = (
            f"\U0001f534 Gilbertus CRITICAL\n"
            f"{title}\n"
            f"{message}"
        )
        if fix_command:
            wa_msg += f"\n\nFix: {fix_command}"
        wa_msg += '\n\nReply "ok" to acknowledge.'

        self._send_whatsapp(wa_msg)


# ------------------------------------------------------------------
# CLI entry point (for cron)
# ------------------------------------------------------------------

def _cli():
    """CLI for cron jobs."""
    import argparse

    parser = argparse.ArgumentParser(description="Alert Manager CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("repeat", help="Repeat unacknowledged critical alerts")
    ack_p = sub.add_parser("ack", help="Acknowledge alert by ID")
    ack_p.add_argument("alert_id", type=int)
    ack_all_p = sub.add_parser("ack-all", help="Acknowledge all critical alerts")
    ack_all_p.add_argument("--category", type=str, default=None)
    sub.add_parser("list", help="List active alerts")

    args = parser.parse_args()
    mgr = AlertManager()

    if args.command == "repeat":
        count = mgr.repeat_unacknowledged()
        print(f"Repeated {count} critical alerts")
    elif args.command == "ack":
        ok = mgr.acknowledge(args.alert_id)
        print(f"Acknowledged: {ok}")
    elif args.command == "ack-all":
        count = mgr.acknowledge_latest(args.category)
        print(f"Acknowledged {count} alerts")
    elif args.command == "list":
        alerts = mgr.get_active()
        for a in alerts:
            ack = "ACK" if a["acknowledged"] else "OPEN"
            print(f"[{a['id']}] T{a['tier']} {ack} {a['category']}: {a['title']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
