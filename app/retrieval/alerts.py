"""
Proactive alerts system for Gilbertus Albans.

Scans the database for conditions that deserve Sebastian's attention:
- Decisions without follow-up (stale >7 days)
- Conflict spikes (>3 conflict events in a rolling week)
- Missing communication (active entities gone silent 30+ days)
- Health pattern clustering

Usage:
    python -m app.retrieval.alerts
    python -m app.retrieval.alerts --date 2026-03-20
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.db.postgres import get_pg_connection

logger = logging.getLogger(__name__)


# ============================================================
# Alert detectors
# ============================================================

def detect_decisions_without_followup(
    reference_date: str,
) -> list[dict[str, Any]]:
    """
    Find decision/commitment/plan events older than 7 days that have no
    related event (sharing at least one entity) after them.
    """
    query = """
    WITH decision_events AS (
        SELECT
            e.id AS event_id,
            e.event_type,
            e.event_time,
            e.summary,
            array_agg(DISTINCT ee.entity_id) FILTER (WHERE ee.entity_id IS NOT NULL)
                AS entity_ids
        FROM events e
        LEFT JOIN event_entities ee ON ee.event_id = e.id
        WHERE e.event_type IN ('decision', 'commitment', 'plan', 'deadline')
          AND e.event_time < %s::timestamptz - INTERVAL '7 days'
          AND e.event_time >= %s::timestamptz - INTERVAL '60 days'
        GROUP BY e.id, e.event_type, e.event_time, e.summary
    ),
    followups AS (
        SELECT DISTINCT de.event_id
        FROM decision_events de
        JOIN event_entities ee_later ON ee_later.entity_id = ANY(de.entity_ids)
        JOIN events e_later ON e_later.id = ee_later.event_id
        WHERE e_later.event_time > de.event_time
          AND e_later.id != de.event_id
    )
    SELECT
        de.event_id,
        de.event_type,
        de.event_time,
        de.summary
    FROM decision_events de
    LEFT JOIN followups fu ON fu.event_id = de.event_id
    WHERE fu.event_id IS NULL
      AND de.entity_ids IS NOT NULL
    ORDER BY de.event_time DESC
    LIMIT 20
    """

    ref = reference_date
    alerts: list[dict[str, Any]] = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (ref, ref))
            rows = cur.fetchall()

    for row in rows:
        event_id, event_type, event_time, summary = row
        days_ago = (
            datetime.fromisoformat(reference_date)
            - (event_time.replace(tzinfo=None) if event_time else datetime.fromisoformat(reference_date))
        ).days

        alerts.append({
            "alert_type": "decision_no_followup",
            "severity": "high" if days_ago > 14 else "medium",
            "title": f"Brak follow-upu: {event_type} sprzed {days_ago} dni",
            "description": (
                f"Wydarzenie [{event_type}] z {event_time.strftime('%Y-%m-%d') if event_time else '?'}: "
                f"\"{summary[:200]}\" nie ma powiazanego dalszego dzialania."
            ),
            "evidence": json.dumps({
                "event_id": event_id,
                "event_type": event_type,
                "event_time": event_time.isoformat() if event_time else None,
                "days_ago": days_ago,
            }, ensure_ascii=False, default=str),
        })

    return alerts


def detect_conflict_spikes(
    reference_date: str,
) -> list[dict[str, Any]]:
    """
    Find weeks where more than 3 conflict events occurred.
    Looks at the last 4 rolling weeks.
    """
    query = """
    SELECT
        date_trunc('week', e.event_time) AS week_start,
        COUNT(*) AS conflict_count,
        array_agg(e.summary ORDER BY e.event_time) AS summaries,
        array_agg(e.id ORDER BY e.event_time) AS event_ids
    FROM events e
    WHERE e.event_type = 'conflict'
      AND e.event_time >= %s::timestamptz - INTERVAL '28 days'
      AND e.event_time < %s::timestamptz + INTERVAL '1 day'
    GROUP BY date_trunc('week', e.event_time)
    HAVING COUNT(*) > 3
    ORDER BY week_start DESC
    """

    alerts: list[dict[str, Any]] = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (reference_date, reference_date))
            rows = cur.fetchall()

    for row in rows:
        week_start, conflict_count, summaries, event_ids = row
        week_label = week_start.strftime("%Y-%m-%d") if week_start else "?"

        trimmed_summaries = [
            (s[:120] + "...") if len(s) > 120 else s
            for s in (summaries or [])[:5]
        ]

        alerts.append({
            "alert_type": "conflict_spike",
            "severity": "high" if conflict_count >= 5 else "medium",
            "title": f"Skok konfliktow: {conflict_count} w tygodniu od {week_label}",
            "description": (
                f"{conflict_count} wydarzen typu 'conflict' w tygodniu od {week_label}. "
                f"Przyklady: {'; '.join(trimmed_summaries)}"
            ),
            "evidence": json.dumps({
                "week_start": week_label,
                "conflict_count": conflict_count,
                "event_ids": event_ids[:10],
            }, ensure_ascii=False, default=str),
        })

    return alerts


def detect_missing_communication(
    reference_date: str,
) -> list[dict[str, Any]]:
    """
    Find person/organization entities that appeared at least once a month
    for the prior 3 months but have had no activity in the last 30 days.
    """
    query = """
    WITH monthly_activity AS (
        SELECT
            en.id AS entity_id,
            en.canonical_name,
            en.entity_type,
            date_trunc('month', e.event_time) AS month,
            COUNT(*) AS event_count
        FROM entities en
        JOIN event_entities ee ON ee.entity_id = en.id
        JOIN events e ON e.id = ee.event_id
        WHERE en.entity_type IN ('person', 'organization')
          AND e.event_time >= %s::timestamptz - INTERVAL '120 days'
          AND e.event_time < %s::timestamptz - INTERVAL '30 days'
        GROUP BY en.id, en.canonical_name, en.entity_type, date_trunc('month', e.event_time)
    ),
    consistently_active AS (
        SELECT
            entity_id,
            canonical_name,
            entity_type,
            COUNT(DISTINCT month) AS active_months,
            SUM(event_count) AS total_events
        FROM monthly_activity
        GROUP BY entity_id, canonical_name, entity_type
        HAVING COUNT(DISTINCT month) >= 2
    ),
    recent_activity AS (
        SELECT DISTINCT ee.entity_id
        FROM event_entities ee
        JOIN events e ON e.id = ee.event_id
        WHERE e.event_time >= %s::timestamptz - INTERVAL '30 days'
          AND e.event_time < %s::timestamptz + INTERVAL '1 day'
    )
    SELECT
        ca.canonical_name,
        ca.entity_type,
        ca.active_months,
        ca.total_events
    FROM consistently_active ca
    LEFT JOIN recent_activity ra ON ra.entity_id = ca.entity_id
    WHERE ra.entity_id IS NULL
    ORDER BY ca.total_events DESC
    LIMIT 15
    """

    alerts: list[dict[str, Any]] = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (
                reference_date, reference_date,
                reference_date, reference_date,
            ))
            rows = cur.fetchall()

    for row in rows:
        name, entity_type, active_months, total_events = row

        alerts.append({
            "alert_type": "missing_communication",
            "severity": "medium" if active_months >= 3 else "low",
            "title": f"Brak kontaktu: {name} ({entity_type})",
            "description": (
                f"{name} byl aktywny przez {active_months} miesiecy "
                f"({total_events} wydarzen), ale nie pojawil sie od 30+ dni."
            ),
            "evidence": json.dumps({
                "canonical_name": name,
                "entity_type": entity_type,
                "active_months": active_months,
                "total_events": total_events,
            }, ensure_ascii=False, default=str),
        })

    return alerts


def detect_health_clustering(
    reference_date: str,
) -> list[dict[str, Any]]:
    """
    Detect clusters of health-related events (3+ within 7 days).
    """
    query = """
    WITH health_events AS (
        SELECT
            e.id,
            e.event_time,
            e.summary
        FROM events e
        WHERE e.event_type IN ('health', 'wellbeing', 'medical')
          AND e.event_time >= %s::timestamptz - INTERVAL '30 days'
          AND e.event_time < %s::timestamptz + INTERVAL '1 day'
        ORDER BY e.event_time
    ),
    windowed AS (
        SELECT
            h1.id,
            h1.event_time,
            h1.summary,
            COUNT(*) OVER (
                ORDER BY h1.event_time
                RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
            ) AS events_in_window
        FROM health_events h1
    )
    SELECT
        id,
        event_time,
        summary,
        events_in_window
    FROM windowed
    WHERE events_in_window >= 3
    ORDER BY event_time DESC
    """

    alerts: list[dict[str, Any]] = []
    seen_windows: set[str] = set()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (reference_date, reference_date))
            rows = cur.fetchall()

    for row in rows:
        event_id, event_time, summary, count_in_window = row
        week_key = event_time.strftime("%Y-W%W") if event_time else "?"

        if week_key in seen_windows:
            continue
        seen_windows.add(week_key)

        alerts.append({
            "alert_type": "health_clustering",
            "severity": "high" if count_in_window >= 5 else "medium",
            "title": (
                f"Klaster zdrowotny: {count_in_window} wydarzen "
                f"w tygodniu {week_key}"
            ),
            "description": (
                f"{count_in_window} wydarzen zdrowotnych w ciagu 7 dni "
                f"(do {event_time.strftime('%Y-%m-%d') if event_time else '?'}). "
                f"Ostatnie: \"{summary[:200]}\""
            ),
            "evidence": json.dumps({
                "week_key": week_key,
                "count_in_window": count_in_window,
                "latest_event_id": event_id,
                "latest_event_time": event_time.isoformat() if event_time else None,
            }, ensure_ascii=False, default=str),
        })

    return alerts


# ============================================================
# Save alerts
# ============================================================

def save_alerts(alerts: list[dict[str, Any]]) -> list[int]:
    """
    Insert alerts into the alerts table. Deduplicates by checking if an
    identical (alert_type, title) alert already exists and is still active.
    Returns list of inserted alert IDs.
    """
    if not alerts:
        return []

    inserted_ids: list[int] = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for alert in alerts:
                # Skip if an identical active alert already exists
                cur.execute(
                    """
                    SELECT id FROM alerts
                    WHERE alert_type = %s
                      AND title = %s
                      AND is_active = TRUE
                    LIMIT 1
                    """,
                    (alert["alert_type"], alert["title"]),
                )
                existing = cur.fetchall()
                if existing:
                    continue

                cur.execute(
                    """
                    INSERT INTO alerts (alert_type, severity, title, description, evidence)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        alert["alert_type"],
                        alert["severity"],
                        alert["title"],
                        alert["description"],
                        alert.get("evidence"),
                    ),
                )
                rows = cur.fetchall()
                if rows:
                    inserted_ids.append(rows[0][0])

        conn.commit()

    return inserted_ids


# ============================================================
# Fetch alerts
# ============================================================

def get_alerts(
    active_only: bool = True,
    alert_type: str | None = None,
    severity: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch alerts from the database with optional filters."""
    conditions: list[str] = []
    params: list[Any] = []

    if active_only:
        conditions.append("is_active = TRUE")

    # Exclude suppressed alert types
    conditions.append(
        "alert_type NOT IN (SELECT alert_type FROM alert_suppressions)"
    )

    if alert_type:
        conditions.append("alert_type = %s")
        params.append(alert_type)

    if severity:
        conditions.append("severity = %s")
        params.append(severity)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
    SELECT id, alert_type, severity, title, description, evidence,
           is_active, created_at
    FROM alerts
    {where_clause}
    ORDER BY
        CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
        created_at DESC
    LIMIT %s
    """
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    return [
        {
            "alert_id": row[0],
            "alert_type": row[1],
            "severity": row[2],
            "title": row[3],
            "description": row[4],
            "evidence": row[5],
            "is_active": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
        }
        for row in rows
    ]


# ============================================================
# Main pipeline
# ============================================================

def run_alerts_check(
    date: str | None = None,
) -> dict[str, Any]:
    """
    Run all alert detectors, save new alerts, return summary.

    Args:
        date: Reference date (YYYY-MM-DD). Defaults to today.

    Returns:
        Dict with counts per alert type and list of new alerts.
    """
    if date is None:
        date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    logger.info("Running alerts check for reference date: %s", date)

    all_alerts: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    detectors = [
        ("decision_no_followup", detect_decisions_without_followup),
        ("conflict_spike", detect_conflict_spikes),
        ("missing_communication", detect_missing_communication),
        ("health_clustering", detect_health_clustering),
    ]

    for name, detector_fn in detectors:
        try:
            detected = detector_fn(date)
            counts[name] = len(detected)
            all_alerts.extend(detected)
            logger.info("Detector %s found %d alerts", name, len(detected))
        except Exception:
            logger.exception("Detector %s failed", name)
            counts[name] = -1

    inserted_ids = save_alerts(all_alerts)

    logger.info(
        "Alerts check complete: %d detected, %d new saved",
        len(all_alerts), len(inserted_ids),
    )

    return {
        "date": date,
        "detected_counts": counts,
        "total_detected": len(all_alerts),
        "new_saved": len(inserted_ids),
        "new_alert_ids": inserted_ids,
        "alerts": all_alerts,
    }


# ============================================================
# CLI
# ============================================================

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    date = None
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--date":
            date = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] in ("--help", "-h"):
            print(__doc__)
            sys.exit(0)
        else:
            raise ValueError(f"Unknown argument: {sys.argv[i]}")

    result = run_alerts_check(date=date)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
