"""
Standing Order Effectiveness Monitor — measures which standing orders work.

For each standing order: response rate, avg response time, effective vs ineffective topics.
Recommends: change channel, modify scope, sunset order.

Cron: weekly (part of communication_effectiveness.sh)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

from typing import Any

from app.db.postgres import get_pg_connection


# ================================================================
# Database
# ================================================================

_tables_ensured = False


def _ensure_tables():
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Ensure response tracking columns exist on sent_communications
            cur.execute("""
                ALTER TABLE sent_communications
                    ADD COLUMN IF NOT EXISTS response_received BOOLEAN DEFAULT FALSE
            """)
            cur.execute("""
                ALTER TABLE sent_communications
                    ADD COLUMN IF NOT EXISTS response_time_hours NUMERIC
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS standing_order_metrics (
                    id BIGSERIAL PRIMARY KEY,
                    order_id BIGINT NOT NULL REFERENCES standing_orders(id),
                    period_start DATE NOT NULL,
                    period_end DATE NOT NULL,
                    sent_count INT DEFAULT 0,
                    response_count INT DEFAULT 0,
                    avg_response_hours NUMERIC,
                    response_rate NUMERIC(3,2),
                    effective_topics TEXT[],
                    ineffective_topics TEXT[],
                    recommendation TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(order_id, period_start)
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_standing_order_metrics_order
                    ON standing_order_metrics(order_id)
            """)
        conn.commit()
    _tables_ensured = True


# ================================================================
# Core functions
# ================================================================

def analyze_order_effectiveness(order_id: int, days: int = 30) -> dict[str, Any]:
    """Analyze effectiveness of a single standing order over a period.

    Returns: {order_id, channel, recipient, scope, sent_count, response_count,
              response_rate, avg_response_hours, recommendation}
    """
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Get order info
            cur.execute("""
                SELECT id, channel, recipient_pattern, topic_scope
                FROM standing_orders
                WHERE id = %s
            """, (order_id,))
            rows = cur.fetchall()
            if not rows:
                log.warning("standing_order_not_found", order_id=order_id)
                return {"error": f"Standing order #{order_id} not found"}

            _, channel, recipient, scope = rows[0]

            # Count sends
            cur.execute("""
                SELECT COUNT(*) FROM sent_communications
                WHERE standing_order_id = %s
                  AND sent_at > NOW() - make_interval(days => %s)
            """, (order_id, days))
            rows = cur.fetchall()
            sent_count = rows[0][0] if rows else 0

            # Count responses
            cur.execute("""
                SELECT COUNT(*) FROM sent_communications
                WHERE standing_order_id = %s
                  AND sent_at > NOW() - make_interval(days => %s)
                  AND response_received = TRUE
            """, (order_id, days))
            rows = cur.fetchall()
            response_count = rows[0][0] if rows else 0

            # Avg response time
            cur.execute("""
                SELECT AVG(response_time_hours) FROM sent_communications
                WHERE standing_order_id = %s
                  AND response_received = TRUE
                  AND sent_at > NOW() - make_interval(days => %s)
            """, (order_id, days))
            rows = cur.fetchall()
            avg_response_hours = float(rows[0][0]) if rows and rows[0][0] else None

    # Calculate rate
    response_rate = round(response_count / sent_count, 2) if sent_count > 0 else 0.0

    # Generate recommendation
    if sent_count == 0:
        recommendation = "Brak wysłanych wiadomości — sprawdź czy order jest aktywnie używany"
    elif response_rate < 0.20:
        recommendation = "Rozważ zmianę kanału lub anulowanie"
    elif response_rate < 0.50:
        recommendation = "Skuteczność poniżej 50% — sprawdź czy tematyka jest trafna"
    elif response_rate < 0.80:
        recommendation = "Średnia skuteczność — monitoruj dalej"
    else:
        recommendation = "Skuteczny — utrzymaj"

    result = {
        "order_id": order_id,
        "channel": channel,
        "recipient": recipient,
        "scope": scope,
        "sent_count": sent_count,
        "response_count": response_count,
        "response_rate": response_rate,
        "avg_response_hours": avg_response_hours,
        "recommendation": recommendation,
    }

    log.info("order_effectiveness_analyzed", **result)
    return result


def run_all_order_analysis(days: int = 30) -> list[dict[str, Any]]:
    """Analyze all active standing orders and save metrics."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM standing_orders WHERE active = TRUE ORDER BY id
            """)
            order_ids = [r[0] for r in cur.fetchall()]

    if not order_ids:
        log.info("no_active_standing_orders")
        return []

    results = []
    for oid in order_ids:
        analysis = analyze_order_effectiveness(oid, days=days)
        if "error" in analysis:
            continue
        results.append(analysis)

        # Save metrics
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO standing_order_metrics
                        (order_id, period_start, period_end, sent_count, response_count,
                         avg_response_hours, response_rate, recommendation)
                    VALUES (%s, CURRENT_DATE - make_interval(days => %s), CURRENT_DATE,
                            %s, %s, %s, %s, %s)
                    ON CONFLICT (order_id, period_start) DO UPDATE SET
                        sent_count = EXCLUDED.sent_count,
                        response_count = EXCLUDED.response_count,
                        avg_response_hours = EXCLUDED.avg_response_hours,
                        response_rate = EXCLUDED.response_rate,
                        recommendation = EXCLUDED.recommendation,
                        created_at = NOW()
                """, (oid, days, analysis["sent_count"], analysis["response_count"],
                      analysis["avg_response_hours"], analysis["response_rate"],
                      analysis["recommendation"]))
            conn.commit()

    log.info("all_orders_analyzed", count=len(results))
    return results


def get_order_recommendations() -> list[dict[str, Any]]:
    """Return orders with recommendations for improvement, sorted by impact."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT som.order_id, so.channel, so.recipient_pattern, so.topic_scope,
                       som.sent_count, som.response_count, som.response_rate,
                       som.avg_response_hours, som.recommendation
                FROM standing_order_metrics som
                JOIN standing_orders so ON so.id = som.order_id
                WHERE so.active = TRUE
                  AND som.created_at = (
                      SELECT MAX(created_at) FROM standing_order_metrics
                      WHERE order_id = som.order_id
                  )
                  AND som.response_rate < 0.80
                ORDER BY som.response_rate ASC, som.sent_count DESC
            """)
            rows = cur.fetchall()

    return [
        {
            "order_id": r[0],
            "channel": r[1],
            "recipient": r[2],
            "scope": r[3],
            "sent_count": r[4],
            "response_count": r[5],
            "response_rate": float(r[6]) if r[6] else 0.0,
            "avg_response_hours": float(r[7]) if r[7] else None,
            "recommendation": r[8],
        }
        for r in rows
    ]
