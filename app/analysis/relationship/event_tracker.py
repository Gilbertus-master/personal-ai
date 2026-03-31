# PRIVATE — nie eksponować w Omnius ani publicznym API
from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from app.config.timezone import APP_TIMEZONE as CET
from app.db.postgres import get_pg_connection

log = structlog.get_logger("rel.events")

EVENT_TYPES = {"date", "conflict", "milestone", "concern", "positive", "negative", "boundary", "communication"}


def log_event(
    partner_id: int,
    event_type: str,
    title: str,
    description: str | None = None,
    sentiment: float | None = None,
) -> int:
    """Zaloguj zdarzenie w relacji. Zwraca id."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Invalid event_type: {event_type}. Allowed: {EVENT_TYPES}")
    if sentiment is not None and not (-5.0 <= sentiment <= 5.0):
        raise ValueError("Sentiment must be between -5.0 and 5.0")

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO rel_events (partner_id, event_type, title, description, sentiment)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (partner_id, event_type, title, description, sentiment),
            )
            event_id = cur.fetchall()[0][0]
            conn.commit()
            # Log only type + sentiment, never content
            log.info("rel.event.logged", event_type=event_type, sentiment=sentiment)
            return event_id


def get_events(
    partner_id: int = 1,
    days: int = 7,
    event_type: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Pobierz zdarzenia z ostatnich N dni."""
    since = datetime.now(CET) - timedelta(days=days)
    params: list = [partner_id, since]
    type_filter = ""
    if event_type:
        type_filter = " AND event_type = %s"
        params.append(event_type)
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT id, event_type, title, description, sentiment,
                           created_at
                    FROM rel_events
                    WHERE partner_id = %s AND created_at >= %s{type_filter}
                    ORDER BY created_at DESC
                    LIMIT %s""",
                params,
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            for r in rows:
                r["created_at"] = str(r["created_at"])
            return rows


def get_sentiment_stats(partner_id: int = 1, days: int = 7) -> dict:
    """Statystyki sentymentu z ostatnich N dni."""
    since = datetime.now(CET) - timedelta(days=days)
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT
                       COUNT(*) as total,
                       COUNT(*) FILTER (WHERE sentiment > 0) as positive,
                       COUNT(*) FILTER (WHERE sentiment < 0) as negative,
                       COUNT(*) FILTER (WHERE sentiment = 0 OR sentiment IS NULL) as neutral,
                       COALESCE(AVG(sentiment), 0) as avg_sentiment
                   FROM rel_events
                   WHERE partner_id = %s AND created_at >= %s""",
                (partner_id, since),
            )
            row = cur.fetchone()
            return {
                "total": row[0],
                "positive": row[1],
                "negative": row[2],
                "neutral": row[3],
                "avg_sentiment": float(row[4]),
                "positivity_ratio": round(row[1] / max(row[2], 1), 2),
            }
