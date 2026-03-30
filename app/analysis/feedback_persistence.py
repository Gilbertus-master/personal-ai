"""
Feedback Persistence — stores answer evaluation results and tracks trends.

Saves eval scores from the Evaluator-Optimizer pattern for trend analysis.
Identifies weak areas where answer quality is consistently low.
"""
from __future__ import annotations

from typing import Optional

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
                CREATE TABLE IF NOT EXISTS answer_evaluations (
                    id BIGSERIAL PRIMARY KEY,
                    ask_run_id BIGINT REFERENCES ask_runs(id) ON DELETE SET NULL,
                    relevance NUMERIC(3,2) NOT NULL,
                    grounding NUMERIC(3,2) NOT NULL,
                    depth NUMERIC(3,2) NOT NULL,
                    overall NUMERIC(3,2) NOT NULL,
                    feedback TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_answer_evaluations_run
                ON answer_evaluations(ask_run_id);
                CREATE INDEX IF NOT EXISTS idx_answer_evaluations_created
                ON answer_evaluations(created_at);
                CREATE INDEX IF NOT EXISTS idx_answer_evaluations_overall
                ON answer_evaluations(overall);
            """)
        conn.commit()
    log.info("feedback_persistence_schema_ensured")
    _tables_ensured = True


# ---------------------------------------------------------------------------
# Core: save evaluation
# ---------------------------------------------------------------------------

def save_answer_evaluation(
    ask_run_id: Optional[int],
    relevance: float,
    grounding: float,
    depth: float,
    overall: float,
    feedback: Optional[str] = None,
) -> Optional[int]:
    """Save an answer evaluation result. Returns evaluation id or None on error."""
    _ensure_tables()
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO answer_evaluations
                        (ask_run_id, relevance, grounding, depth, overall, feedback)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (ask_run_id, relevance, grounding, depth, overall, feedback))
                eval_id = cur.fetchall()[0][0]
            conn.commit()
        log.info("answer_evaluation_saved",
                 eval_id=eval_id, ask_run_id=ask_run_id, overall=overall)
        return eval_id
    except Exception as e:
        log.error("answer_evaluation_save_failed", error=str(e))
        return None


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

def get_evaluation_trends(days: int = 30) -> dict:
    """Get evaluation score trends over the last N days.

    Returns daily averages for each axis plus overall trend direction.
    """
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Daily averages
            cur.execute("""
                SELECT DATE(created_at) as day,
                       AVG(relevance) as avg_relevance,
                       AVG(grounding) as avg_grounding,
                       AVG(depth) as avg_depth,
                       AVG(overall) as avg_overall,
                       COUNT(*) as count
                FROM answer_evaluations
                WHERE created_at > NOW() - (%s * INTERVAL '1 day')
                GROUP BY DATE(created_at)
                ORDER BY day DESC
            """, (days,))
            daily = []
            for row in cur.fetchall():
                daily.append({
                    "date": str(row[0]),
                    "avg_relevance": round(float(row[1]), 3),
                    "avg_grounding": round(float(row[2]), 3),
                    "avg_depth": round(float(row[3]), 3),
                    "avg_overall": round(float(row[4]), 3),
                    "count": row[5],
                })

            # Overall stats
            cur.execute("""
                SELECT AVG(relevance), AVG(grounding), AVG(depth), AVG(overall),
                       COUNT(*),
                       MIN(overall), MAX(overall),
                       PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY overall)
                FROM answer_evaluations
                WHERE created_at > NOW() - (%s * INTERVAL '1 day')
            """, (days,))
            stats_row = cur.fetchone()

    if not stats_row or stats_row[4] == 0:
        return {
            "days": days,
            "total_evaluations": 0,
            "daily": [],
            "trend": "insufficient_data",
        }

    # Determine trend: compare first half vs second half
    trend = "stable"
    if len(daily) >= 4:
        mid = len(daily) // 2
        first_half = sum(d["avg_overall"] for d in daily[mid:]) / len(daily[mid:])
        second_half = sum(d["avg_overall"] for d in daily[:mid]) / len(daily[:mid])
        diff = second_half - first_half
        if diff > 0.05:
            trend = "improving"
        elif diff < -0.05:
            trend = "declining"

    return {
        "days": days,
        "total_evaluations": stats_row[4],
        "avg_relevance": round(float(stats_row[0]), 3),
        "avg_grounding": round(float(stats_row[1]), 3),
        "avg_depth": round(float(stats_row[2]), 3),
        "avg_overall": round(float(stats_row[3]), 3),
        "min_overall": round(float(stats_row[5]), 3),
        "max_overall": round(float(stats_row[6]), 3),
        "p25_overall": round(float(stats_row[7]), 3),
        "trend": trend,
        "daily": daily,
    }


# ---------------------------------------------------------------------------
# Weak areas
# ---------------------------------------------------------------------------

def get_weak_areas(threshold: float = 0.5, days: int = 30) -> list:
    """Identify question types and patterns with consistently low scores.

    Returns list of dicts with weak area details.
    """
    _ensure_tables()

    weak: list[dict] = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Weak by question_type (join with ask_runs)
            cur.execute("""
                SELECT ar.question_type,
                       AVG(ae.overall) as avg_score,
                       COUNT(*) as count,
                       AVG(ae.relevance) as avg_rel,
                       AVG(ae.grounding) as avg_gnd,
                       AVG(ae.depth) as avg_dep
                FROM answer_evaluations ae
                JOIN ask_runs ar ON ar.id = ae.ask_run_id
                WHERE ae.created_at > NOW() - (%s * INTERVAL '1 day')
                  AND ae.ask_run_id IS NOT NULL
                GROUP BY ar.question_type
                HAVING AVG(ae.overall) < %s AND COUNT(*) >= 3
                ORDER BY avg_score ASC
            """, (days, threshold))
            for row in cur.fetchall():
                weak.append({
                    "type": "question_type",
                    "value": row[0],
                    "avg_score": round(float(row[1]), 3),
                    "count": row[2],
                    "weakest_axis": _weakest_axis(
                        float(row[3]), float(row[4]), float(row[5])
                    ),
                })

            # Weak by source_type
            cur.execute("""
                SELECT arm.source_type,
                       AVG(ae.overall) as avg_score,
                       COUNT(*) as count
                FROM answer_evaluations ae
                JOIN ask_runs ar ON ar.id = ae.ask_run_id
                JOIN ask_run_matches arm ON arm.ask_run_id = ar.id
                WHERE ae.created_at > NOW() - (%s * INTERVAL '1 day')
                  AND ae.ask_run_id IS NOT NULL
                  AND arm.source_type IS NOT NULL
                GROUP BY arm.source_type
                HAVING AVG(ae.overall) < %s AND COUNT(*) >= 3
                ORDER BY avg_score ASC
            """, (days, threshold))
            for row in cur.fetchall():
                weak.append({
                    "type": "source_type",
                    "value": row[0],
                    "avg_score": round(float(row[1]), 3),
                    "count": row[2],
                })

    return weak


def _weakest_axis(relevance: float, grounding: float, depth: float) -> str:
    axes = {"relevance": relevance, "grounding": grounding, "depth": depth}
    return min(axes, key=axes.get)
