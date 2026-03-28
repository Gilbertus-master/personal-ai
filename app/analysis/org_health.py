"""
Organizational Health Score — one number measuring organization health.

Score 1-100, calculated weekly from 8 dimensions:
1. Commitment delivery rate (25%)
2. Sentiment average (15%)
3. Communication response rate (15%)
4. Delegation effectiveness (15%)
5. Decision follow-up rate (10%)
6. Calendar deep work % (10%)
7. Blind spots count (5%)
8. Predictive alerts count (5%)

Cron: weekly (part of weekly_analysis.sh)
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
from datetime import datetime, timedelta, timezone

from app.db.postgres import get_pg_connection

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _ensure_tables() -> None:
    """Create org_health_scores table if not exists."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS org_health_scores (
                    id BIGSERIAL PRIMARY KEY,
                    week_start DATE NOT NULL UNIQUE,
                    overall_score NUMERIC(4,1) NOT NULL,
                    dimension_scores JSONB NOT NULL,
                    trend_vs_last_week NUMERIC(4,1),
                    top_risks TEXT[],
                    top_improvements TEXT[],
                    details JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_org_health_week
                    ON org_health_scores(week_start);
            """)
        conn.commit()
    log.info("org_health.tables_ensured")


# ---------------------------------------------------------------------------
# Dimension calculators
# ---------------------------------------------------------------------------

def _calc_commitment_rate() -> dict:
    """Commitment delivery rate (25%) — target >85%."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'fulfilled') as fulfilled,
                        COUNT(*) FILTER (WHERE status IN ('fulfilled', 'broken', 'overdue')) as total
                    FROM commitments
                    WHERE updated_at > NOW() - INTERVAL '30 days'
                """)
                rows = cur.fetchall()
                row = rows[0] if rows else None
                rate = row[0] / max(row[1], 1)
                score = min(rate / 0.85, 1.0) * 100
                return {"score": round(score, 1), "value": round(rate, 3), "weight": 0.25,
                        "label": "Commitment delivery rate"}
    except Exception:
        log.warning("org_health.commitment_rate_failed", exc_info=True)
        return {"score": 50.0, "value": None, "weight": 0.25,
                "label": "Commitment delivery rate"}


def _calc_sentiment() -> dict:
    """Sentiment average (15%) — target 3.5/5."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT AVG(sentiment_score)
                    FROM sentiment_scores
                    WHERE created_at > NOW() - INTERVAL '7 days'
                """)
                rows = cur.fetchall()
                row = rows[0] if rows else None
                if row and row[0] is not None:
                    avg_sent = float(row[0])
                    # Map 1-5 scale: 3.5 = 100 points, 1.0 = 0, 5.0 = 100
                    score = min(avg_sent / 3.5, 1.0) * 100
                    return {"score": round(score, 1), "value": round(avg_sent, 2), "weight": 0.15,
                            "label": "Sentiment average"}
                return {"score": 50.0, "value": None, "weight": 0.15,
                        "label": "Sentiment average"}
    except Exception:
        log.warning("org_health.sentiment_failed", exc_info=True)
        return {"score": 50.0, "value": None, "weight": 0.15,
                "label": "Sentiment average"}


def _calc_response_rate() -> dict:
    """Communication response rate (15%) — target >80%."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE response_received = TRUE) as responded,
                        COUNT(*) as total
                    FROM sent_communications
                    WHERE sent_at > NOW() - INTERVAL '7 days'
                """)
                rows = cur.fetchall()
                row = rows[0] if rows else None
                if row and row[1] > 0:
                    rate = row[0] / row[1]
                    score = min(rate / 0.80, 1.0) * 100
                    return {"score": round(score, 1), "value": round(rate, 3), "weight": 0.15,
                            "label": "Communication response rate"}
                return {"score": 50.0, "value": None, "weight": 0.15,
                        "label": "Communication response rate"}
    except Exception:
        log.warning("org_health.response_rate_failed", exc_info=True)
        return {"score": 50.0, "value": None, "weight": 0.15,
                "label": "Communication response rate"}


def _calc_delegation() -> dict:
    """Delegation effectiveness (15%) — target >80%."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'completed') as completed,
                        COUNT(*) FILTER (WHERE status IN ('completed', 'overdue', 'failed', 'in_progress')) as total
                    FROM delegation_tasks
                    WHERE updated_at > NOW() - INTERVAL '30 days'
                """)
                rows = cur.fetchall()
                row = rows[0] if rows else None
                if row and row[1] > 0:
                    rate = row[0] / row[1]
                    score = min(rate / 0.80, 1.0) * 100
                    return {"score": round(score, 1), "value": round(rate, 3), "weight": 0.15,
                            "label": "Delegation effectiveness"}
                return {"score": 50.0, "value": None, "weight": 0.15,
                        "label": "Delegation effectiveness"}
    except Exception:
        log.warning("org_health.delegation_failed", exc_info=True)
        return {"score": 50.0, "value": None, "weight": 0.15,
                "label": "Delegation effectiveness"}


def _calc_decision_followup() -> dict:
    """Decision follow-up rate (10%) — target >80%."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE review_status = 'reviewed') as reviewed,
                        COUNT(*) as total
                    FROM decisions
                    WHERE created_at > NOW() - INTERVAL '30 days'
                """)
                rows = cur.fetchall()
                row = rows[0] if rows else None
                if row and row[1] > 0:
                    rate = row[0] / row[1]
                    score = min(rate / 0.80, 1.0) * 100
                    return {"score": round(score, 1), "value": round(rate, 3), "weight": 0.10,
                            "label": "Decision follow-up rate"}
                return {"score": 50.0, "value": None, "weight": 0.10,
                        "label": "Decision follow-up rate"}
    except Exception:
        log.warning("org_health.decision_followup_failed", exc_info=True)
        return {"score": 50.0, "value": None, "weight": 0.10,
                "label": "Decision follow-up rate"}


def _calc_deep_work() -> dict:
    """Calendar deep work % (10%) — target >30%."""
    # Calendar data not yet available — use placeholder
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Check if calendar_events table exists and has data
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'calendar_events'
                    )
                """)
                exists_rows = cur.fetchall()
                if exists_rows and exists_rows[0][0]:
                    cur.execute("""
                        SELECT
                            COUNT(*) FILTER (WHERE event_type = 'focus_time') as focus,
                            COUNT(*) as total
                        FROM calendar_events
                        WHERE start_time > NOW() - INTERVAL '7 days'
                    """)
                    rows = cur.fetchall()
                    row = rows[0] if rows else None
                    if row and row[1] > 0:
                        rate = row[0] / row[1]
                        score = min(rate / 0.30, 1.0) * 100
                        return {"score": round(score, 1), "value": round(rate, 3), "weight": 0.10,
                                "label": "Calendar deep work %"}
        return {"score": 50.0, "value": None, "weight": 0.10,
                "label": "Calendar deep work %"}
    except Exception:
        log.warning("org_health.deep_work_failed", exc_info=True)
        return {"score": 50.0, "value": None, "weight": 0.10,
                "label": "Calendar deep work %"}


def _calc_blind_spots() -> dict:
    """Blind spots count (5%) — target <2."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Count persons with very few interactions (potential blind spots)
                cur.execute("""
                    SELECT COUNT(DISTINCT person_name) FROM (
                        SELECT person_name, COUNT(*) as cnt
                        FROM entities
                        WHERE entity_type = 'person'
                          AND created_at > NOW() - INTERVAL '30 days'
                        GROUP BY person_name
                        HAVING COUNT(*) < 2
                    ) sub
                """)
                rows = cur.fetchall()
                row = rows[0] if rows else None
                blind_count = row[0] if row else 0
                # Target <2: 0 spots = 100, 2 = 50, 5+ = 0
                score = max(0, 100 - blind_count * 25)
                return {"score": min(round(score, 1), 100), "value": blind_count, "weight": 0.05,
                        "label": "Blind spots count"}
    except Exception:
        log.warning("org_health.blind_spots_failed", exc_info=True)
        return {"score": 50.0, "value": None, "weight": 0.05,
                "label": "Blind spots count"}


def _calc_predictive_alerts() -> dict:
    """Predictive alerts count (5%) — target 0 active."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM predictive_alerts
                    WHERE status = 'active'
                """)
                rows = cur.fetchall()
                row = rows[0] if rows else None
                alert_count = row[0] if row else 0
                # Target 0: 0 = 100, 1 = 80, 3 = 40, 5+ = 0
                score = max(0, 100 - alert_count * 20)
                return {"score": min(round(score, 1), 100), "value": alert_count, "weight": 0.05,
                        "label": "Active predictive alerts"}
    except Exception:
        log.warning("org_health.predictive_alerts_failed", exc_info=True)
        return {"score": 50.0, "value": None, "weight": 0.05,
                "label": "Active predictive alerts"}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def calculate_health_score() -> dict:
    """Calculate overall health score from 8 dimensions."""
    _ensure_tables()

    dimensions = {
        "commitment_rate": _calc_commitment_rate(),
        "sentiment": _calc_sentiment(),
        "response_rate": _calc_response_rate(),
        "delegation": _calc_delegation(),
        "decision_followup": _calc_decision_followup(),
        "deep_work": _calc_deep_work(),
        "blind_spots": _calc_blind_spots(),
        "predictive_alerts": _calc_predictive_alerts(),
    }

    # Weighted sum
    overall = sum(d["score"] * d["weight"] for d in dimensions.values())
    overall = round(overall, 1)

    # Identify top risks (low scoring dimensions)
    sorted_dims = sorted(dimensions.items(), key=lambda x: x[1]["score"])
    top_risks = [
        f"{d[1]['label']}: {d[1]['score']}/100"
        for d in sorted_dims[:3]
        if d[1]["score"] < 70
    ]

    # Identify improvements (high scoring dimensions)
    top_improvements = [
        f"{d[1]['label']}: {d[1]['score']}/100"
        for d in reversed(sorted_dims)
        if d[1]["score"] >= 80
    ][:3]

    result = {
        "overall_score": overall,
        "dimensions": dimensions,
        "top_risks": top_risks,
        "top_improvements": top_improvements,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }

    log.info("org_health.calculated", overall_score=overall,
             risks=len(top_risks), improvements=len(top_improvements))
    return result


def get_health_trend(weeks: int = 8) -> dict:
    """Return health score trend over recent weeks."""
    _ensure_tables()
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT week_start, overall_score, dimension_scores,
                       trend_vs_last_week, top_risks, top_improvements
                FROM org_health_scores
                ORDER BY week_start DESC
                LIMIT %s
                """,
                (weeks,),
            )
            rows = cur.fetchall()

    if not rows:
        return {
            "current_score": None,
            "trend": "no_data",
            "history": [],
            "best_week": None,
            "worst_week": None,
        }

    history = [
        {
            "week": str(r[0]),
            "score": float(r[1]),
            "trend": float(r[3]) if r[3] is not None else None,
        }
        for r in rows
    ]

    scores = [(str(r[0]), float(r[1])) for r in rows]
    current = scores[0][1]
    best = max(scores, key=lambda x: x[1])
    worst = min(scores, key=lambda x: x[1])

    # Determine trend from last 3 data points
    if len(scores) >= 3:
        recent = [s[1] for s in scores[:3]]
        if recent[0] > recent[1] > recent[2]:
            trend = "improving"
        elif recent[0] < recent[1] < recent[2]:
            trend = "declining"
        else:
            trend = "stable"
    elif len(scores) >= 2:
        trend = "improving" if scores[0][1] > scores[1][1] else "declining"
    else:
        trend = "stable"

    return {
        "current_score": current,
        "trend": trend,
        "history": list(reversed(history)),
        "best_week": {"week": best[0], "score": best[1]},
        "worst_week": {"week": worst[0], "score": worst[1]},
    }


def run_health_assessment() -> dict:
    """Main pipeline: calculate -> compare with last week -> save -> return."""
    _ensure_tables()
    log.info("org_health.assessment_start")

    # Calculate current score
    health = calculate_health_score()

    # Get Monday of current week as week_start
    today = datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=today.weekday())

    # Get last week's score for trend
    trend_vs_last: float | None = None
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT overall_score FROM org_health_scores
                    WHERE week_start < %s
                    ORDER BY week_start DESC LIMIT 1
                    """,
                    (week_start,),
                )
                rows = cur.fetchall()
                row = rows[0] if rows else None
                if row:
                    trend_vs_last = round(health["overall_score"] - float(row[0]), 1)
    except Exception:
        log.warning("org_health.trend_calc_failed", exc_info=True)

    # Save to DB
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO org_health_scores
                        (week_start, overall_score, dimension_scores, trend_vs_last_week,
                         top_risks, top_improvements, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (week_start) DO UPDATE SET
                        overall_score = EXCLUDED.overall_score,
                        dimension_scores = EXCLUDED.dimension_scores,
                        trend_vs_last_week = EXCLUDED.trend_vs_last_week,
                        top_risks = EXCLUDED.top_risks,
                        top_improvements = EXCLUDED.top_improvements,
                        details = EXCLUDED.details,
                        created_at = NOW()
                    RETURNING id
                    """,
                    (
                        week_start,
                        health["overall_score"],
                        json.dumps(health["dimensions"], default=str),
                        trend_vs_last,
                        health["top_risks"],
                        health["top_improvements"],
                        json.dumps({"calculated_at": health["calculated_at"]}, default=str),
                    ),
                )
                rows = cur.fetchall()
                saved_id = rows[0][0] if rows else None
            conn.commit()
        log.info("org_health.saved", id=saved_id, week_start=str(week_start))
    except Exception:
        log.error("org_health.save_failed", exc_info=True)
        saved_id = None

    result = {
        "id": saved_id,
        "week_start": str(week_start),
        "overall_score": health["overall_score"],
        "trend_vs_last_week": trend_vs_last,
        "dimensions": health["dimensions"],
        "top_risks": health["top_risks"],
        "top_improvements": health["top_improvements"],
    }

    log.info("org_health.assessment_complete", overall_score=health["overall_score"],
             trend=trend_vs_last)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--trend" in sys.argv:
        idx = sys.argv.index("--trend")
        weeks = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) and sys.argv[idx + 1].isdigit() else 8
        result = get_health_trend(weeks)
    elif "--score" in sys.argv:
        result = calculate_health_score()
    else:
        result = run_health_assessment()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
