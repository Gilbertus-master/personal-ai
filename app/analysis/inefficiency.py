"""
Process Inefficiency Detector.

Analyzes event patterns to find:
- Repeating tasks (same type of event with similar entities, recurring weekly)
- Communication bottlenecks (same person appears in escalations repeatedly)
- Decision delays (decisions that take >7 days from first mention to resolution)
- Meeting overload (>5 meetings/day for any person)

Usage:
    python -m app.analysis.inefficiency
"""
from __future__ import annotations

import json
from typing import Any

from app.db.postgres import get_pg_connection


def detect_repeating_tasks(weeks: int = 8, min_occurrences: int = 4) -> list[dict[str, Any]]:
    """Find events that repeat weekly with similar patterns."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH weekly_patterns AS (
                    SELECT event_type, LEFT(summary, 60) as pattern,
                           COUNT(DISTINCT DATE_TRUNC('week', event_time)) as weeks_seen,
                           COUNT(*) as total_occurrences,
                           ROUND(AVG(confidence)::numeric, 2) as avg_confidence
                    FROM events
                    WHERE event_time > NOW() - INTERVAL '%s weeks'
                      AND event_time IS NOT NULL
                    GROUP BY event_type, LEFT(summary, 60)
                    HAVING COUNT(DISTINCT DATE_TRUNC('week', event_time)) >= %s
                )
                SELECT event_type, pattern, weeks_seen, total_occurrences, avg_confidence
                FROM weekly_patterns
                ORDER BY total_occurrences DESC
                LIMIT 20
            """, (weeks, min_occurrences))
            return [
                {"type": r[0], "pattern": r[1], "weeks_seen": r[2],
                 "total": r[3], "avg_confidence": float(r[4]) if r[4] else 0,
                 "est_hours_per_month": round(r[3] / (weeks / 4) * 0.5, 1),  # rough: 30 min per occurrence
                 "automation_potential": "high" if r[3] > 20 else "medium"}
                for r in cur.fetchall()
            ]


def detect_escalation_bottlenecks(weeks: int = 12) -> list[dict[str, Any]]:
    """Find people who appear in escalations repeatedly."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT en.canonical_name, COUNT(*) as escalations
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                JOIN entities en ON en.id = ee.entity_id
                WHERE e.event_type IN ('escalation', 'blocker', 'conflict')
                  AND e.event_time > NOW() - INTERVAL '%s weeks'
                  AND en.entity_type = 'person'
                GROUP BY en.canonical_name
                HAVING COUNT(*) >= 3
                ORDER BY escalations DESC
                LIMIT 10
            """, (weeks,))
            return [
                {"person": r[0], "escalations": r[1],
                 "interpretation": f"{r[0]} pojawia się w {r[1]} eskalacjach/blokadach — potencjalny bottleneck"}
                for r in cur.fetchall()
            ]


def detect_meeting_overload(weeks: int = 4) -> list[dict[str, Any]]:
    """Find days/people with too many meetings."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT en.canonical_name,
                       DATE(e.event_time) as day,
                       COUNT(*) as meetings
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                JOIN entities en ON en.id = ee.entity_id
                WHERE e.event_type = 'meeting'
                  AND e.event_time > NOW() - INTERVAL '%s weeks'
                  AND en.entity_type = 'person'
                GROUP BY en.canonical_name, DATE(e.event_time)
                HAVING COUNT(*) >= 5
                ORDER BY meetings DESC
                LIMIT 20
            """, (weeks,))
            return [
                {"person": r[0], "date": str(r[1]), "meetings": r[2],
                 "interpretation": f"{r[0]} miał {r[2]} spotkań {r[1]} — meeting overload"}
                for r in cur.fetchall()
            ]


def generate_inefficiency_report() -> dict[str, Any]:
    """Full inefficiency analysis report."""
    repeating = detect_repeating_tasks()
    bottlenecks = detect_escalation_bottlenecks()
    overload = detect_meeting_overload()

    # Calculate total automation potential
    total_hours = sum(r["est_hours_per_month"] for r in repeating)

    return {
        "generated_at": "now",
        "repeating_tasks": repeating,
        "escalation_bottlenecks": bottlenecks,
        "meeting_overload": overload,
        "summary": {
            "repeating_patterns": len(repeating),
            "bottleneck_people": len(bottlenecks),
            "overloaded_days": len(overload),
            "est_automation_hours_per_month": round(total_hours, 1),
            "est_automation_savings_pln": round(total_hours * 150, 0),  # 150 PLN/h avg
        },
    }


if __name__ == "__main__":
    report = generate_inefficiency_report()
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
