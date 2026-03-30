"""
Feedback Calibration — self-adjusting relevance thresholds.

Tracks: which briefs/alerts Sebastian reads, responds to, or ignores.
Adjusts: relevance thresholds, alert priority, brief section ordering.

Data sources:
- WhatsApp read receipts (via OpenClaw session tracking)
- Response patterns (task_monitor classification)
- Insight review status (insights.reviewed)
- Alert acknowledgment (market_alerts.acknowledged)

Cron: 0 22 * * 0 (weekly Sunday 23:00 CET — calibration cycle)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
from datetime import datetime, timezone
from typing import Any

from app.db.postgres import get_pg_connection


def _ensure_tables():
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS engagement_metrics (
                    id BIGSERIAL PRIMARY KEY,
                    metric_date DATE NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_value NUMERIC,
                    details JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(metric_date, metric_type)
                );

                CREATE TABLE IF NOT EXISTS calibration_settings (
                    id BIGSERIAL PRIMARY KEY,
                    setting_key TEXT NOT NULL UNIQUE,
                    setting_value JSONB NOT NULL,
                    reason TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            conn.commit()


def measure_engagement(days: int = 7) -> dict[str, Any]:
    """Measure Sebastian's engagement with Gilbertus outputs."""
    _ensure_tables()
    metrics = {}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Insight review rate
            cur.execute("""
                SELECT COUNT(*) FILTER (WHERE reviewed = true) as reviewed,
                       COUNT(*) as total
                FROM insights WHERE created_at > NOW() - INTERVAL '%s days'
            """, (days,))
            r = cur.fetchone()
            metrics["insight_review_rate"] = r[0] / max(r[1], 1)
            metrics["insights_total"] = r[1]
            metrics["insights_reviewed"] = r[0]

            # Alert acknowledgment rate
            cur.execute("""
                SELECT COUNT(*) FILTER (WHERE acknowledged = true) as acked,
                       COUNT(*) as total
                FROM market_alerts WHERE created_at > NOW() - INTERVAL '%s days'
            """, (days,))
            r = cur.fetchone()
            metrics["alert_ack_rate"] = r[0] / max(r[1], 1)
            metrics["alerts_total"] = r[1]

            # WhatsApp command usage
            cur.execute("""
                SELECT COUNT(*) FROM documents d
                JOIN sources s ON d.source_id = s.id
                WHERE s.source_type = 'whatsapp_live'
                AND d.created_at > NOW() - INTERVAL '%s days'
            """, (days,))
            metrics["whatsapp_messages"] = cur.fetchall()[0][0]

            # Decision logging rate
            cur.execute("""
                SELECT COUNT(*) FROM decisions
                WHERE created_at > NOW() - INTERVAL '%s days'
            """, (days,))
            metrics["decisions_logged"] = cur.fetchall()[0][0]

    # Store daily metric
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO engagement_metrics (metric_date, metric_type, metric_value, details)
                VALUES (%s, 'weekly_engagement', %s, %s)
                ON CONFLICT (metric_date, metric_type) DO UPDATE SET
                    metric_value = EXCLUDED.metric_value,
                    details = EXCLUDED.details
            """, (today, metrics.get("insight_review_rate", 0), json.dumps(metrics)))
            conn.commit()

    log.info("engagement_measured", review_rate=metrics.get("insight_review_rate"),
             alert_ack_rate=metrics.get("alert_ack_rate"),
             wa_messages=metrics.get("whatsapp_messages"))

    return metrics


def get_calibration_setting(key: str, default: Any = None) -> Any:
    """Get a calibration setting."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM calibration_settings WHERE setting_key = %s", (key,))
            rows = cur.fetchall()
            if rows:
                return rows[0][0]
    return default


def update_calibration(key: str, value: Any, reason: str = ""):
    """Update a calibration setting."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO calibration_settings (setting_key, setting_value, reason)
                VALUES (%s, %s, %s)
                ON CONFLICT (setting_key) DO UPDATE SET
                    setting_value = EXCLUDED.setting_value,
                    reason = EXCLUDED.reason,
                    updated_at = NOW()
            """, (key, json.dumps(value), reason))
            conn.commit()


def run_calibration_cycle() -> dict[str, Any]:
    """Weekly calibration: adjust thresholds based on engagement."""
    _ensure_tables()
    metrics = measure_engagement(days=7)

    adjustments = []

    # If review rate < 30%, insights are too noisy → raise confidence threshold
    review_rate = metrics.get("insight_review_rate", 0)
    if review_rate < 0.3 and metrics.get("insights_total", 0) > 5:
        current = get_calibration_setting("min_insight_confidence", 0.5)
        new_val = min(current + 0.1, 0.9) if isinstance(current, (int, float)) else 0.6
        update_calibration("min_insight_confidence", new_val,
                          f"Review rate {review_rate:.0%} < 30%, raising threshold")
        adjustments.append(f"min_insight_confidence: {current} → {new_val}")

    # If alert ack rate < 20%, alerts are too frequent → raise relevance threshold
    ack_rate = metrics.get("alert_ack_rate", 0)
    if ack_rate < 0.2 and metrics.get("alerts_total", 0) > 3:
        current = get_calibration_setting("min_alert_relevance", 80)
        new_val = min(current + 5, 95) if isinstance(current, (int, float)) else 85
        update_calibration("min_alert_relevance", new_val,
                          f"Alert ack rate {ack_rate:.0%} < 20%, raising threshold")
        adjustments.append(f"min_alert_relevance: {current} → {new_val}")

    # If WhatsApp usage is high, system is working well
    if metrics.get("whatsapp_messages", 0) > 20:
        update_calibration("system_engagement", "high",
                          f"{metrics['whatsapp_messages']} WA messages in 7 days")

    log.info("calibration_done", adjustments=len(adjustments))

    return {
        "metrics": metrics,
        "adjustments": adjustments,
        "settings": {
            "min_insight_confidence": get_calibration_setting("min_insight_confidence", 0.5),
            "min_alert_relevance": get_calibration_setting("min_alert_relevance", 80),
            "system_engagement": get_calibration_setting("system_engagement", "unknown"),
        },
    }
