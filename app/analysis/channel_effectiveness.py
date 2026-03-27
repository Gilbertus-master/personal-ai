"""
Channel Effectiveness Analyzer — which communication channel works best with each person.

Analyzes: email vs Teams vs WhatsApp per person.
Output: optimal channel per person, response rates per channel.

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

def _ensure_tables():
    """Ensure response tracking columns exist on sent_communications."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE sent_communications
                    ADD COLUMN IF NOT EXISTS response_received BOOLEAN DEFAULT FALSE
            """)
            cur.execute("""
                ALTER TABLE sent_communications
                    ADD COLUMN IF NOT EXISTS response_time_hours NUMERIC
            """)
        conn.commit()


# ================================================================
# Core functions
# ================================================================

def analyze_channel_effectiveness(days: int = 60) -> dict[str, Any]:
    """Analyze response rates per person per channel.

    Returns dict keyed by person with channel breakdown and recommendations.
    """
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    sc.recipient,
                    sc.channel,
                    COUNT(*) as sent,
                    COUNT(*) FILTER (WHERE sc.response_received) as responded,
                    AVG(sc.response_time_hours) FILTER (WHERE sc.response_received) as avg_hours,
                    ROUND(
                        COUNT(*) FILTER (WHERE sc.response_received)::numeric
                        / NULLIF(COUNT(*), 0), 2
                    ) as rate
                FROM sent_communications sc
                WHERE sc.sent_at > NOW() - make_interval(days => %s)
                GROUP BY sc.recipient, sc.channel
                HAVING COUNT(*) >= 3
                ORDER BY sc.recipient, rate DESC
            """, (days,))
            rows = cur.fetchall()

    if not rows:
        log.info("no_channel_data", days=days)
        return {"people": {}, "summary": "Brak wystarczających danych do analizy kanałów"}

    # Group by person
    people: dict[str, dict[str, Any]] = {}
    for recipient, channel, sent, responded, avg_hours, rate in rows:
        if recipient not in people:
            people[recipient] = {"channels": [], "best_channel": None, "worst_channel": None}

        channel_data = {
            "channel": channel,
            "sent": sent,
            "responded": responded,
            "avg_hours": round(float(avg_hours), 1) if avg_hours else None,
            "rate": float(rate) if rate else 0.0,
        }
        people[recipient]["channels"].append(channel_data)

    # Determine best/worst per person
    for person, data in people.items():
        channels = data["channels"]
        if len(channels) >= 1:
            best = max(channels, key=lambda c: c["rate"])
            worst = min(channels, key=lambda c: c["rate"])
            data["best_channel"] = best["channel"]
            data["best_rate"] = best["rate"]
            if len(channels) >= 2:
                data["worst_channel"] = worst["channel"]
                data["worst_rate"] = worst["rate"]
                data["recommendation"] = (
                    f"Use {best['channel']} for {person} — "
                    f"{int(best['rate'] * 100)}% response rate"
                    f" vs {int(worst['rate'] * 100)}% {worst['channel']}"
                )
            else:
                data["recommendation"] = (
                    f"Only {best['channel']} data available for {person} — "
                    f"{int(best['rate'] * 100)}% response rate"
                )

    log.info("channel_effectiveness_analyzed", people_count=len(people))
    return {"people": people, "summary": f"Przeanalizowano {len(people)} osób z {len(rows)} kombinacji kanałów"}


def get_optimal_channel(person: str) -> dict[str, Any]:
    """For a specific person, return the best channel to use.

    Returns: {person, best_channel, best_rate, worst_channel, worst_rate, recommendation}
    """
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    sc.channel,
                    COUNT(*) as sent,
                    COUNT(*) FILTER (WHERE sc.response_received) as responded,
                    AVG(sc.response_time_hours) FILTER (WHERE sc.response_received) as avg_hours,
                    ROUND(
                        COUNT(*) FILTER (WHERE sc.response_received)::numeric
                        / NULLIF(COUNT(*), 0), 2
                    ) as rate
                FROM sent_communications sc
                WHERE sc.recipient ILIKE %s
                GROUP BY sc.channel
                HAVING COUNT(*) >= 2
                ORDER BY rate DESC
            """, (f"%{person}%",))
            rows = cur.fetchall()

    if not rows:
        return {
            "person": person,
            "error": "Brak wystarczających danych",
            "recommendation": f"Brak danych o kanałach dla {person}",
        }

    channels = [
        {
            "channel": r[0],
            "sent": r[1],
            "responded": r[2],
            "avg_hours": round(float(r[3]), 1) if r[3] else None,
            "rate": float(r[4]) if r[4] else 0.0,
        }
        for r in rows
    ]

    best = channels[0]  # Already sorted DESC by rate
    worst = channels[-1] if len(channels) > 1 else None

    result = {
        "person": person,
        "best_channel": best["channel"],
        "best_rate": best["rate"],
        "channels": channels,
    }

    if worst and worst["channel"] != best["channel"]:
        result["worst_channel"] = worst["channel"]
        result["worst_rate"] = worst["rate"]
        result["recommendation"] = (
            f"Use {best['channel']} for {person} — "
            f"{int(best['rate'] * 100)}% response rate"
            f" vs {int(worst['rate'] * 100)}% {worst['channel']}"
        )
    else:
        result["recommendation"] = (
            f"Use {best['channel']} for {person} — "
            f"{int(best['rate'] * 100)}% response rate"
        )

    log.info("optimal_channel_found", **{k: v for k, v in result.items() if k != "channels"})
    return result


def run_channel_analysis() -> dict[str, Any]:
    """Full analysis for all people with enough data. Return summary."""
    analysis = analyze_channel_effectiveness(days=60)

    people = analysis.get("people", {})
    recommendations = []
    for person, data in people.items():
        if data.get("recommendation"):
            recommendations.append({
                "person": person,
                "best_channel": data.get("best_channel"),
                "best_rate": data.get("best_rate"),
                "recommendation": data["recommendation"],
            })

    result = {
        "people_analyzed": len(people),
        "recommendations": recommendations,
        "summary": analysis.get("summary", ""),
    }

    log.info("channel_analysis_complete", people=len(people), recommendations=len(recommendations))
    return result
