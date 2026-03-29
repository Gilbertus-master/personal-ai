"""
Delegation Effectiveness — measures task completion rate per person
using commitment data. All SQL-based, no LLM needed.

Functions:
- calculate_delegation_score(person_name, months): per-person effectiveness metrics
- get_delegation_ranking(): all people ranked by completion rate
- run_delegation_report(): full report with ranking and trends
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from dotenv import load_dotenv

from app.db.postgres import get_pg_connection

load_dotenv()

log = structlog.get_logger(__name__)


def calculate_delegation_score(person_name: str, months: int = 3) -> dict[str, Any]:
    """Calculate delegation effectiveness score for a person.

    Returns:
        total_commitments, fulfilled/broken/overdue/open counts,
        completion_rate, avg_days_to_complete, on_time_rate, trend
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Core counts over the period
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'fulfilled') as fulfilled,
                    COUNT(*) FILTER (WHERE status = 'broken') as broken,
                    COUNT(*) FILTER (WHERE status = 'overdue') as overdue,
                    COUNT(*) FILTER (WHERE status = 'open') as open,
                    COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled
                FROM commitments
                WHERE LOWER(person_name) = LOWER(%s)
                  AND created_at > NOW() - make_interval(months => %s)
            """, (person_name, months))
            row = cur.fetchone()
            total, fulfilled, broken, overdue, open_count, cancelled = row

            if total == 0:
                return {
                    "person_name": person_name,
                    "total_commitments": 0,
                    "message": "no commitments found",
                }

            # Completion rate: fulfilled / (fulfilled + broken + overdue)
            denominator = fulfilled + broken + overdue
            completion_rate = round(fulfilled / denominator, 3) if denominator > 0 else None

            # Average days to complete (for fulfilled commitments with deadline)
            cur.execute("""
                SELECT AVG(EXTRACT(DAY FROM (updated_at - created_at)))
                FROM commitments
                WHERE LOWER(person_name) = LOWER(%s)
                  AND status = 'fulfilled'
                  AND created_at > NOW() - make_interval(months => %s)
            """, (person_name, months))
            avg_days_row = cur.fetchone()
            avg_days = round(float(avg_days_row[0]), 1) if avg_days_row and avg_days_row[0] else None

            # On-time rate: fulfilled before deadline / total fulfilled with deadline
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE updated_at <= deadline) as on_time,
                    COUNT(*) as with_deadline
                FROM commitments
                WHERE LOWER(person_name) = LOWER(%s)
                  AND status = 'fulfilled'
                  AND deadline IS NOT NULL
                  AND created_at > NOW() - make_interval(months => %s)
            """, (person_name, months))
            ot_row = cur.fetchone()
            on_time, with_deadline = ot_row
            on_time_rate = round(on_time / with_deadline, 3) if with_deadline > 0 else None

            # Trend: compare last month vs previous month
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (
                        WHERE status = 'fulfilled'
                          AND created_at > NOW() - INTERVAL '1 month'
                    ) as recent_fulfilled,
                    COUNT(*) FILTER (
                        WHERE status IN ('fulfilled', 'broken', 'overdue')
                          AND created_at > NOW() - INTERVAL '1 month'
                    ) as recent_total,
                    COUNT(*) FILTER (
                        WHERE status = 'fulfilled'
                          AND created_at > NOW() - INTERVAL '2 months'
                          AND created_at <= NOW() - INTERVAL '1 month'
                    ) as prev_fulfilled,
                    COUNT(*) FILTER (
                        WHERE status IN ('fulfilled', 'broken', 'overdue')
                          AND created_at > NOW() - INTERVAL '2 months'
                          AND created_at <= NOW() - INTERVAL '1 month'
                    ) as prev_total
                FROM commitments
                WHERE LOWER(person_name) = LOWER(%s)
            """, (person_name,))
            trend_row = cur.fetchone()
            recent_fulfilled, recent_total, prev_fulfilled, prev_total = trend_row

            recent_rate = recent_fulfilled / recent_total if recent_total > 0 else None
            prev_rate = prev_fulfilled / prev_total if prev_total > 0 else None

            if recent_rate is not None and prev_rate is not None:
                diff = recent_rate - prev_rate
                if diff > 0.05:
                    trend = "improving"
                elif diff < -0.05:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"

    return {
        "person_name": person_name,
        "months": months,
        "total_commitments": total,
        "fulfilled_count": fulfilled,
        "broken_count": broken,
        "overdue_count": overdue,
        "open_count": open_count,
        "cancelled_count": cancelled,
        "completion_rate": completion_rate,
        "avg_days_to_complete": avg_days,
        "on_time_rate": on_time_rate,
        "trend": trend,
    }


def get_delegation_ranking() -> list[dict[str, Any]]:
    """All people ranked by completion rate (descending)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    person_name,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'fulfilled') as fulfilled,
                    COUNT(*) FILTER (WHERE status = 'broken') as broken,
                    COUNT(*) FILTER (WHERE status = 'overdue') as overdue,
                    COUNT(*) FILTER (WHERE status = 'open') as open_count
                FROM commitments
                WHERE created_at > NOW() - INTERVAL '3 months'
                GROUP BY person_name
                HAVING COUNT(*) >= 2
                ORDER BY
                    CASE WHEN (COUNT(*) FILTER (WHERE status IN ('fulfilled', 'broken', 'overdue'))) > 0
                         THEN COUNT(*) FILTER (WHERE status = 'fulfilled')::FLOAT
                              / (COUNT(*) FILTER (WHERE status IN ('fulfilled', 'broken', 'overdue')))
                         ELSE 0
                    END DESC,
                    COUNT(*) DESC
            """)
            rows = cur.fetchall()

    ranking = []
    for i, r in enumerate(rows, 1):
        person_name, total, fulfilled, broken, overdue, open_count = r
        denominator = fulfilled + broken + overdue
        completion_rate = round(fulfilled / denominator, 3) if denominator > 0 else None
        ranking.append({
            "rank": i,
            "person_name": person_name,
            "total": total,
            "fulfilled": fulfilled,
            "broken": broken,
            "overdue": overdue,
            "open": open_count,
            "completion_rate": completion_rate,
        })

    return ranking


def run_delegation_report() -> dict[str, Any]:
    """Full report with ranking and individual trends."""
    log.info("delegation_report_start")

    ranking = get_delegation_ranking()

    # Get trends for top people
    detailed = []
    for entry in ranking[:15]:
        score = calculate_delegation_score(entry["person_name"], months=3)
        detailed.append(score)

    # Summary stats
    total_people = len(ranking)
    if ranking:
        avg_rate = sum(
            r["completion_rate"] for r in ranking if r["completion_rate"] is not None
        ) / max(1, sum(1 for r in ranking if r["completion_rate"] is not None))
    else:
        avg_rate = None

    # Identify best/worst performers
    performers_with_rate = [r for r in ranking if r["completion_rate"] is not None]
    best = performers_with_rate[:3] if performers_with_rate else []
    worst = performers_with_rate[-3:] if len(performers_with_rate) > 3 else []

    result = {
        "status": "ok",
        "total_people_tracked": total_people,
        "avg_completion_rate": round(avg_rate, 3) if avg_rate is not None else None,
        "best_performers": best,
        "worst_performers": worst,
        "ranking": ranking,
        "detailed_scores": detailed,
    }

    log.info("delegation_report_complete", people=total_people)
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        score = calculate_delegation_score(sys.argv[1])
        print(json.dumps(score, ensure_ascii=False, indent=2, default=str))
    else:
        result = run_delegation_report()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
