"""
Threshold Optimizer — auto-tune alert thresholds and brief sections based on feedback.

Uses answer evaluation trends and alert interaction data to optimize:
- Alert thresholds (too many alerts = noise, too few = missing signals)
- Brief sections (which sections get read, which get skipped)
- Generate optimization report
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_tables_ensured = False
def _ensure_tables() -> None:
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS threshold_optimization_log (
                    id BIGSERIAL PRIMARY KEY,
                    optimization_type TEXT NOT NULL,
                    parameter_name TEXT NOT NULL,
                    old_value NUMERIC,
                    new_value NUMERIC,
                    reason TEXT,
                    applied BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_threshold_opt_type
                ON threshold_optimization_log(optimization_type);
                CREATE INDEX IF NOT EXISTS idx_threshold_opt_created
                ON threshold_optimization_log(created_at);
            """)
        conn.commit()
    _tables_ensured = True


# ---------------------------------------------------------------------------
# Alert threshold optimization
# ---------------------------------------------------------------------------

def optimize_alert_thresholds(days: int = 30) -> list[dict]:
    """Analyze alert patterns and suggest threshold adjustments.

    Looks at:
    - Alert volume per type (too many = raise threshold)
    - Alert acknowledgment rate (low ack = possibly irrelevant)
    - Time-to-acknowledge (slow = low priority)
    """
    _ensure_tables()
    suggestions: list[dict] = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Alert volume and ack rate by type
            cur.execute("""
                SELECT alert_type,
                       COUNT(*) as total,
                       COUNT(*) FILTER (WHERE acknowledged = TRUE) as acked,
                       AVG(EXTRACT(EPOCH FROM (acknowledged_at - created_at)) / 3600)
                           FILTER (WHERE acknowledged = TRUE) as avg_ack_hours
                FROM alerts
                WHERE created_at > NOW() - (%s * INTERVAL '1 day')
                GROUP BY alert_type
                HAVING COUNT(*) >= 5
                ORDER BY total DESC
            """, (days,))
            rows = cur.fetchall()

    for alert_type, total, acked, avg_ack_hours in rows:
        ack_rate = acked / total if total > 0 else 0
        daily_avg = total / max(days, 1)

        suggestion: dict[str, Any] | None = None

        # Too many alerts with low ack rate → raise threshold
        if daily_avg > 5 and ack_rate < 0.3:
            suggestion = {
                "optimization_type": "alert_threshold",
                "parameter_name": f"alert_{alert_type}_threshold",
                "direction": "raise",
                "reason": (f"Alert type '{alert_type}': {daily_avg:.1f}/day avg, "
                           f"only {ack_rate:.0%} acknowledged. Consider raising threshold."),
                "current_daily_avg": round(daily_avg, 1),
                "ack_rate": round(ack_rate, 3),
            }
        # Very high ack rate with slow ack → might be good but not urgent
        elif ack_rate > 0.8 and avg_ack_hours and avg_ack_hours > 24:
            suggestion = {
                "optimization_type": "alert_threshold",
                "parameter_name": f"alert_{alert_type}_priority",
                "direction": "lower_priority",
                "reason": (f"Alert type '{alert_type}': high ack rate ({ack_rate:.0%}) "
                           f"but slow response ({avg_ack_hours:.0f}h). "
                           f"Consider batching into daily digest."),
                "ack_rate": round(ack_rate, 3),
                "avg_ack_hours": round(avg_ack_hours, 1),
            }

        if suggestion:
            # Log the suggestion
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO threshold_optimization_log
                            (optimization_type, parameter_name, reason)
                        VALUES (%s, %s, %s)
                    """, (
                        suggestion["optimization_type"],
                        suggestion["parameter_name"],
                        suggestion["reason"],
                    ))
                conn.commit()
            suggestions.append(suggestion)

    log.info("alert_thresholds_optimized", suggestions=len(suggestions))
    return suggestions


# ---------------------------------------------------------------------------
# Brief section optimization
# ---------------------------------------------------------------------------

def optimize_brief_sections(days: int = 30) -> list[dict]:
    """Analyze which brief sections are most/least useful based on feedback.

    Uses answer evaluation scores when queries reference brief content,
    and alert interaction patterns.
    """
    _ensure_tables()
    suggestions: list[dict] = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Check which question types have lowest eval scores
            cur.execute("""
                SELECT ar.question_type,
                       AVG(ae.overall) as avg_score,
                       COUNT(*) as count
                FROM answer_evaluations ae
                JOIN ask_runs ar ON ar.id = ae.ask_run_id
                WHERE ae.created_at > NOW() - (%s * INTERVAL '1 day')
                  AND ae.ask_run_id IS NOT NULL
                GROUP BY ar.question_type
                HAVING COUNT(*) >= 3
                ORDER BY avg_score ASC
            """, (days,))
            weak_types = cur.fetchall()

            for qtype, avg_score, count in weak_types:
                if float(avg_score) < 0.5:
                    suggestion = {
                        "optimization_type": "brief_section",
                        "parameter_name": f"brief_{qtype}_quality",
                        "direction": "improve",
                        "reason": (f"Question type '{qtype}' has avg score {float(avg_score):.2f} "
                                   f"over {count} evaluations. Brief content for this area "
                                   f"may need richer source data or better prompts."),
                        "avg_score": round(float(avg_score), 3),
                        "count": count,
                    }
                    with get_pg_connection() as conn2:
                        with conn2.cursor() as cur2:
                            cur2.execute("""
                                INSERT INTO threshold_optimization_log
                                    (optimization_type, parameter_name, reason)
                                VALUES (%s, %s, %s)
                            """, (
                                suggestion["optimization_type"],
                                suggestion["parameter_name"],
                                suggestion["reason"],
                            ))
                        conn2.commit()
                    suggestions.append(suggestion)

    log.info("brief_sections_optimized", suggestions=len(suggestions))
    return suggestions


# ---------------------------------------------------------------------------
# Optimization report
# ---------------------------------------------------------------------------

def generate_optimization_report(days: int = 30) -> dict:
    """Generate a comprehensive optimization report combining all analyses."""
    _ensure_tables()

    alert_suggestions = optimize_alert_thresholds(days=days)
    brief_suggestions = optimize_brief_sections(days=days)

    # Get recent optimization log
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT optimization_type, parameter_name, reason, applied, created_at
                FROM threshold_optimization_log
                WHERE created_at > NOW() - (%s * INTERVAL '1 day')
                ORDER BY created_at DESC
                LIMIT 20
            """, (days,))
            recent_log = [
                {
                    "type": r[0],
                    "parameter": r[1],
                    "reason": r[2],
                    "applied": r[3],
                    "created_at": str(r[4]),
                }
                for r in cur.fetchall()
            ]

            # Answer quality summary
            cur.execute("""
                SELECT COUNT(*),
                       AVG(overall),
                       COUNT(*) FILTER (WHERE overall < 0.5),
                       COUNT(*) FILTER (WHERE overall >= 0.7)
                FROM answer_evaluations
                WHERE created_at > NOW() - (%s * INTERVAL '1 day')
            """, (days,))
            qual_row = cur.fetchone()

    total_evals = qual_row[0] if qual_row else 0
    quality_summary = {}
    if total_evals > 0:
        quality_summary = {
            "total_evaluations": total_evals,
            "avg_overall": round(float(qual_row[1]), 3) if qual_row[1] else None,
            "low_quality_count": qual_row[2],
            "high_quality_count": qual_row[3],
            "low_quality_rate": round(qual_row[2] / total_evals, 3),
        }

    return {
        "report_date": datetime.now(timezone.utc).isoformat(),
        "period_days": days,
        "alert_suggestions": alert_suggestions,
        "brief_suggestions": brief_suggestions,
        "quality_summary": quality_summary,
        "recent_optimizations": recent_log,
        "total_suggestions": len(alert_suggestions) + len(brief_suggestions),
    }
