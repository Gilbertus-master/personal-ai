"""
Cross-domain correlation engine for Gilbertus Albans.

Finds temporal and entity-level patterns across event types:
- "Weeks with 3+ conflicts → what happened with trades?"
- "Marcin Kulpa: conflict frequency vs decision involvement over time"
- "Communication anomalies per person (deviation from baseline)"

Usage:
    python -m app.analysis.correlation --type temporal --event-a conflict --event-b trade
    python -m app.analysis.correlation --type person --person "Marcin Kulpa"
    python -m app.analysis.correlation --type anomaly
"""
from __future__ import annotations

import json
import sys
from contextlib import nullcontext
from datetime import datetime, timezone
from typing import Any

from app.db.postgres import get_pg_connection


# ============================================================
# 1. Temporal correlation: event_type_a vs event_type_b by week
# ============================================================

def correlate_event_types(
    event_type_a: str,
    event_type_b: str,
    window: str = "week",
    min_periods: int = 4,
    conn: Any = None,
) -> dict[str, Any]:
    """
    Correlate two event types over time windows.
    Returns: co-occurrence data, trend, and insight.
    """
    trunc = "week" if window == "week" else "month"
    if trunc not in ("week", "month"):
        raise ValueError(f"Invalid window: {window}")

    with (get_pg_connection() if conn is None else nullcontext(conn)) as _conn:
        with _conn.cursor() as cur:
            cur.execute(f"""
                WITH periods AS (
                    SELECT DATE_TRUNC('{trunc}', event_time) as period,
                           COUNT(*) FILTER (WHERE event_type = %s) as count_a,
                           COUNT(*) FILTER (WHERE event_type = %s) as count_b
                    FROM events
                    WHERE event_time IS NOT NULL
                      AND event_time > NOW() - INTERVAL '12 months'
                    GROUP BY period
                    HAVING COUNT(*) > 0
                    ORDER BY period
                )
                SELECT period, count_a, count_b FROM periods
            """, (event_type_a, event_type_b))
            rows = cur.fetchall()

    if len(rows) < min_periods:
        return {
            "status": "insufficient_data",
            "message": f"Only {len(rows)} periods found (need {min_periods}+)",
            "event_type_a": event_type_a,
            "event_type_b": event_type_b,
        }

    periods = []
    vals_a = []
    vals_b = []
    for period, count_a, count_b in rows:
        periods.append(period.isoformat() if period else "?")
        vals_a.append(count_a)
        vals_b.append(count_b)

    # Simple correlation: Pearson
    n = len(vals_a)
    mean_a = sum(vals_a) / n
    mean_b = sum(vals_b) / n
    cov = sum((vals_a[i] - mean_a) * (vals_b[i] - mean_b) for i in range(n)) / n
    std_a = (sum((v - mean_a) ** 2 for v in vals_a) / n) ** 0.5
    std_b = (sum((v - mean_b) ** 2 for v in vals_b) / n) ** 0.5

    if std_a == 0 or std_b == 0:
        pearson = 0.0
    else:
        pearson = cov / (std_a * std_b)

    # Find high-a weeks and what happens to b
    threshold_a = mean_a + std_a
    high_a_weeks = [(periods[i], vals_a[i], vals_b[i]) for i in range(n) if vals_a[i] > threshold_a]
    avg_b_when_high_a = sum(w[2] for w in high_a_weeks) / len(high_a_weeks) if high_a_weeks else 0

    return {
        "status": "ok",
        "event_type_a": event_type_a,
        "event_type_b": event_type_b,
        "window": window,
        "periods": n,
        "pearson_correlation": round(pearson, 3),
        "interpretation": _interpret_pearson(pearson, event_type_a, event_type_b),
        "mean_a": round(mean_a, 1),
        "mean_b": round(mean_b, 1),
        "high_a_threshold": round(threshold_a, 1),
        "high_a_weeks_count": len(high_a_weeks),
        "avg_b_when_high_a": round(avg_b_when_high_a, 1),
        "avg_b_overall": round(mean_b, 1),
        "data": [
            {"period": periods[i], event_type_a: vals_a[i], event_type_b: vals_b[i]}
            for i in range(n)
        ],
    }


def _interpret_pearson(r: float, a: str, b: str) -> str:
    if r > 0.7:
        return f"Silna korelacja dodatnia: tygodnie z dużą liczbą {a} mają też dużo {b}."
    if r > 0.3:
        return f"Umiarkowana korelacja dodatnia między {a} a {b}."
    if r > -0.3:
        return f"Brak wyraźnej korelacji między {a} a {b}."
    if r > -0.7:
        return f"Umiarkowana korelacja ujemna: więcej {a} → mniej {b}."
    return f"Silna korelacja ujemna: tygodnie z dużą liczbą {a} mają mało {b}."


# ============================================================
# 2. Person profile: event types over time for a specific person
# ============================================================

def person_event_profile(
    person_name: str,
    months: int = 6,
) -> dict[str, Any]:
    """
    Show a person's involvement across event types over time.
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Find entity ID via fuzzy match
            cur.execute("""
                SELECT id, canonical_name FROM entities
                WHERE entity_type = 'person'
                  AND canonical_name %% %s
                ORDER BY similarity(canonical_name, %s) DESC
                LIMIT 1
            """, (person_name, person_name))
            entity_rows = cur.fetchall()
            if not entity_rows:
                return {"status": "not_found", "person": person_name}

            entity_id = entity_rows[0][0]
            canonical = entity_rows[0][1]

            # Get event profile by week
            cur.execute("""
                SELECT DATE_TRUNC('week', e.event_time) as week,
                       e.event_type,
                       COUNT(*) as count
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                WHERE ee.entity_id = %s
                  AND e.event_time IS NOT NULL
                  AND e.event_time > NOW() - make_interval(months => %s)
                GROUP BY week, event_type
                ORDER BY week DESC, count DESC
            """, (entity_id, months))
            rows = cur.fetchall()

            # Get relationship context
            cur.execute("""
                SELECT r.person_role, r.organization, r.status, r.sentiment
                FROM people p
                JOIN relationships r ON r.person_id = p.id
                WHERE p.entity_id = %s
                LIMIT 1
            """, (entity_id,))
            rel_rows = cur.fetchall()
            rel = rel_rows[0] if rel_rows else (None, None, None, None)

    # Aggregate
    weekly = {}
    type_totals = {}
    for week, event_type, count in rows:
        wk = week.isoformat() if week else "?"
        if wk not in weekly:
            weekly[wk] = {}
        weekly[wk][event_type] = count
        type_totals[event_type] = type_totals.get(event_type, 0) + count

    return {
        "status": "ok",
        "person": canonical,
        "entity_id": entity_id,
        "role": rel[0],
        "organization": rel[1],
        "relationship_status": rel[2],
        "sentiment": rel[3],
        "months_analyzed": months,
        "total_events": sum(type_totals.values()),
        "event_type_breakdown": dict(sorted(type_totals.items(), key=lambda x: -x[1])),
        "weekly_data": [
            {"week": wk, **counts}
            for wk, counts in sorted(weekly.items(), reverse=True)
        ],
    }


# ============================================================
# 3. Anomaly detection: deviation from communication baseline
# ============================================================

def detect_communication_anomalies(
    weeks_baseline: int = 8,
    threshold_stddev: float = 2.0,
    min_baseline_events: int = 5,
    conn: Any = None,
) -> list[dict[str, Any]]:
    """
    Find people whose recent week activity deviates significantly
    from their baseline communication pattern.
    """
    with (get_pg_connection() if conn is None else nullcontext(conn)) as _conn:
        with _conn.cursor() as cur:
            cur.execute("""
                WITH person_weekly AS (
                    SELECT ee.entity_id,
                           en.canonical_name,
                           DATE_TRUNC('week', e.event_time) as week,
                           COUNT(*) as events
                    FROM events e
                    JOIN event_entities ee ON ee.event_id = e.id
                    JOIN entities en ON en.id = ee.entity_id
                    WHERE en.entity_type = 'person'
                      AND e.event_time IS NOT NULL
                      AND e.event_time > NOW() - INTERVAL '%s weeks'
                    GROUP BY ee.entity_id, en.canonical_name, week
                ),
                baselines AS (
                    SELECT entity_id, canonical_name,
                           AVG(events) as avg_events,
                           STDDEV(events) as stddev_events,
                           COUNT(DISTINCT week) as active_weeks,
                           MAX(events) FILTER (WHERE week = DATE_TRUNC('week', NOW())) as current_week
                    FROM person_weekly
                    GROUP BY entity_id, canonical_name
                    HAVING COUNT(DISTINCT week) >= 3
                       AND SUM(events) >= %s
                )
                SELECT canonical_name, avg_events, stddev_events, active_weeks,
                       COALESCE(current_week, 0) as current_week,
                       entity_id
                FROM baselines
                WHERE stddev_events > 0
                  AND ABS(COALESCE(current_week, 0) - avg_events) > %s * stddev_events
                ORDER BY ABS(COALESCE(current_week, 0) - avg_events) / GREATEST(stddev_events, 0.1) DESC
                LIMIT 20
            """, (weeks_baseline, min_baseline_events, threshold_stddev))
            rows = cur.fetchall()

    anomalies = []
    for name, avg_ev, std_ev, weeks, current, entity_id in rows:
        deviation = (current - avg_ev) / std_ev if std_ev > 0 else 0
        direction = "spike" if current > avg_ev else "drop"
        anomalies.append({
            "person": name,
            "entity_id": entity_id,
            "direction": direction,
            "current_week_events": current,
            "baseline_avg": round(float(avg_ev), 1),
            "baseline_stddev": round(float(std_ev), 1),
            "deviation_sigma": round(float(deviation), 1),
            "active_weeks": weeks,
            "interpretation": f"{name}: {direction} ({current} events vs baseline {round(float(avg_ev),1)} ± {round(float(std_ev),1)})",
        })

    return anomalies


# ============================================================
# 4. Full correlation report
# ============================================================

def generate_correlation_report() -> dict[str, Any]:
    """Generate a comprehensive cross-domain correlation report."""

    # Key correlations to check
    correlations = [
        ("conflict", "trade"),
        ("conflict", "decision"),
        ("escalation", "blocker"),
        ("meeting", "decision"),
        ("deadline", "escalation"),
        ("approval", "trade"),
    ]

    with get_pg_connection() as conn:
        results = {}
        for a, b in correlations:
            key = f"{a}_vs_{b}"
            results[key] = correlate_event_types(a, b, conn=conn)

        anomalies = detect_communication_anomalies(conn=conn)

    return {
        "correlations": results,
        "anomalies": anomalies,
        "anomaly_count": len(anomalies),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ============================================================
# API endpoint helper
# ============================================================

def run_correlation(
    correlation_type: str,
    event_type_a: str | None = None,
    event_type_b: str | None = None,
    person: str | None = None,
    window: str = "week",
) -> dict[str, Any]:
    """Unified entry point for API."""
    if correlation_type == "temporal" and event_type_a and event_type_b:
        return correlate_event_types(event_type_a, event_type_b, window)
    elif correlation_type == "person" and person:
        return person_event_profile(person)
    elif correlation_type == "anomaly":
        return {"anomalies": detect_communication_anomalies()}
    elif correlation_type == "report":
        return generate_correlation_report()
    else:
        return {"error": "Invalid correlation type or missing parameters"}


# ============================================================
# CLI
# ============================================================

def main():
    ctype = "report"
    event_a = None
    event_b = None
    person = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--type":
            ctype = args[i + 1]
            i += 2
        elif args[i] == "--event-a":
            event_a = args[i + 1]
            i += 2
        elif args[i] == "--event-b":
            event_b = args[i + 1]
            i += 2
        elif args[i] == "--person":
            person = args[i + 1]
            i += 2
        else:
            i += 1

    result = run_correlation(ctype, event_a, event_b, person)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
