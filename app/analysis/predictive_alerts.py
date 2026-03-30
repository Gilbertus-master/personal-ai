"""
Predictive Alert Engine — Pattern-based predictions using historical data.

SQL-based prediction logic (not LLM-heavy):
1. Escalation risk: conflict/blocker patterns per person
2. Communication gaps: active people going silent
3. Deadline risks: commitments with approaching deadlines

Cron: 0 20 * * 0 (Sunday 20:00 CET — weekly with other analysis)
"""
from __future__ import annotations

import structlog
log = structlog.get_logger(__name__)

import json
from datetime import datetime, timezone
from typing import Any

from app.db.postgres import get_pg_connection


_tables_ensured = False
def _ensure_tables() -> None:
    """Create predictive_alerts table if not exists."""
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS predictive_alerts (
                    id BIGSERIAL PRIMARY KEY,
                    alert_type TEXT NOT NULL,
                    prediction TEXT NOT NULL,
                    probability NUMERIC(3,2) NOT NULL CHECK (probability >= 0 AND probability <= 1),
                    evidence JSONB,
                    time_horizon TEXT,
                    suggested_action TEXT,
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'acknowledged', 'resolved', 'false_positive')),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    resolved_at TIMESTAMPTZ
                );

                CREATE INDEX IF NOT EXISTS idx_pred_alerts_status
                    ON predictive_alerts(status);
            """)
            conn.commit()
    log.info("predictive_alerts.tables_ensured")
    _tables_ensured = True


def predict_escalation_risk(person_name: str) -> dict[str, Any]:
    """Predict escalation risk based on conflict/blocker patterns.

    Logic: Person has 2+ conflicts in last 2 weeks -> probability = conflicts/5 (capped at 0.95)
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Count conflicts in last 2 weeks
            cur.execute("""
                SELECT COUNT(*), array_agg(e.summary ORDER BY e.event_time DESC)
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                JOIN entities en ON en.id = ee.entity_id
                WHERE en.canonical_name ILIKE %s
                  AND e.event_type IN ('conflict', 'escalation', 'blocker')
                  AND e.event_time > NOW() - INTERVAL '14 days'
            """, (f"%{person_name}%",))
            rows = cur.fetchall()
            row = rows[0] if rows else None
            conflict_count = row[0] if row else 0
            conflict_summaries = row[1] if row else []

            # Historical conflict rate (last 3 months for baseline)
            cur.execute("""
                SELECT COUNT(*)
                FROM events e
                JOIN event_entities ee ON ee.event_id = e.id
                JOIN entities en ON en.id = ee.entity_id
                WHERE en.canonical_name ILIKE %s
                  AND e.event_type IN ('conflict', 'escalation', 'blocker')
                  AND e.event_time > NOW() - INTERVAL '3 months'
            """, (f"%{person_name}%",))
            rows = cur.fetchall()
            row = rows[0] if rows else None
            total_3m = row[0] if row else 0

    if conflict_count < 2:
        return {
            "person_name": person_name,
            "alert_type": "escalation_risk",
            "risk": "low",
            "probability": round(min(conflict_count / 5.0, 0.2), 2),
            "recent_conflicts": conflict_count,
            "prediction": None,
        }

    probability = min(conflict_count / 5.0, 0.95)
    avg_monthly = total_3m / 3.0 if total_3m else 0

    prediction = (
        f"{person_name} has {conflict_count} conflicts/blockers in the last 2 weeks "
        f"(vs {avg_monthly:.1f}/month baseline). Escalation likely if unaddressed."
    )

    return {
        "person_name": person_name,
        "alert_type": "escalation_risk",
        "risk": "high" if probability >= 0.6 else "medium",
        "probability": round(probability, 2),
        "recent_conflicts": conflict_count,
        "baseline_monthly": round(avg_monthly, 1),
        "conflict_summaries": conflict_summaries[:5],
        "prediction": prediction,
        "suggested_action": f"Schedule 1:1 with {person_name} to address concerns",
    }


def predict_communication_gaps() -> list[dict[str, Any]]:
    """Predict people going silent who were previously active.

    Logic: Person was active (>5 events/week avg) but last event >7 days ago.
    Probability based on days silent relative to their normal activity.
    """
    gaps = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Find people who were active but went silent
            cur.execute("""
                WITH person_activity AS (
                    SELECT en.canonical_name,
                           COUNT(*) as total_events,
                           MAX(e.event_time) as last_event,
                           MIN(e.event_time) as first_event,
                           COUNT(*) FILTER (
                               WHERE e.event_time > NOW() - INTERVAL '7 days'
                           ) as recent_events,
                           EXTRACT(EPOCH FROM (MAX(e.event_time) - MIN(e.event_time))) / 604800.0
                               as weeks_span
                    FROM entities en
                    JOIN event_entities ee ON ee.entity_id = en.id
                    JOIN events e ON e.id = ee.event_id
                    WHERE en.entity_type = 'person'
                      AND en.canonical_name IS NOT NULL
                      AND en.canonical_name != ''
                      AND e.event_time > NOW() - INTERVAL '3 months'
                    GROUP BY en.canonical_name
                )
                SELECT canonical_name, total_events, last_event,
                       weeks_span,
                       CASE WHEN weeks_span > 0
                            THEN total_events / weeks_span
                            ELSE total_events END as events_per_week,
                       recent_events,
                       EXTRACT(EPOCH FROM (NOW() - last_event)) / 86400.0 as days_silent
                FROM person_activity
                WHERE recent_events = 0
                  AND total_events > 0
                  AND CASE WHEN weeks_span > 0
                           THEN total_events / weeks_span
                           ELSE total_events END > 5
                ORDER BY days_silent DESC
            """)
            rows = cur.fetchall()

    for name, total, last_event, weeks_span, epw, recent, days_silent in rows:
        days_silent = float(days_silent)
        events_per_week = float(epw)

        # Probability increases with days silent, scaled by activity level
        probability = min(0.95, (days_silent - 7) / 14.0 * 0.5 + 0.3)
        if probability < 0.2:
            continue

        gaps.append({
            "person_name": name,
            "alert_type": "communication_gap",
            "probability": round(probability, 2),
            "days_silent": round(days_silent, 1),
            "avg_events_per_week": round(events_per_week, 1),
            "last_event": str(last_event) if last_event else None,
            "prediction": (
                f"{name} was averaging {events_per_week:.1f} events/week "
                f"but has been silent for {days_silent:.0f} days."
            ),
            "suggested_action": f"Check in with {name} — unusual silence detected",
        })

    log.info("predictive_alerts.communication_gaps", count=len(gaps))
    return gaps


def predict_deadline_risks() -> list[dict[str, Any]]:
    """Predict commitments at risk of being missed.

    Logic: Open commitment with deadline within 7 days,
    person has history of late deliveries.
    """
    risks = []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Check if commitments table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'commitments'
                )
            """)
            rows = cur.fetchall()
            row = rows[0] if rows else None
            if not (row and row[0]):
                log.info("predictive_alerts.no_commitments_table")
                return []

            # Open commitments with deadline in next 7 days
            cur.execute("""
                SELECT c.id, c.person_id, c.commitment_text, c.deadline,
                       p.canonical_name
                FROM commitments c
                LEFT JOIN people p ON p.id = c.person_id
                WHERE c.status IN ('open', 'in_progress')
                  AND c.deadline IS NOT NULL
                  AND c.deadline BETWEEN NOW() AND NOW() + INTERVAL '7 days'
                ORDER BY c.deadline
            """)
            upcoming = cur.fetchall()

            for cid, pid, text, deadline, person_name in upcoming:
                # Check person's historical completion rate
                completion_rate = 1.0  # default if no history
                if pid:
                    cur.execute("""
                        SELECT
                            COUNT(*) FILTER (WHERE status = 'completed') as completed,
                            COUNT(*) FILTER (WHERE status IN ('missed', 'overdue')) as missed,
                            COUNT(*) as total
                        FROM commitments
                        WHERE person_id = %s
                          AND status IN ('completed', 'missed', 'overdue')
                    """, (pid,))
                    rows = cur.fetchall()
                    hist = rows[0] if rows else None
                    total_hist = hist[2] if hist else 0
                    if total_hist > 0:
                        completion_rate = hist[0] / total_hist

                # Risk probability: inverse of completion rate, boosted by proximity
                days_until = max(0.1, (deadline - datetime.now(timezone.utc)).total_seconds() / 86400.0)
                proximity_factor = max(0.0, 1.0 - days_until / 7.0)  # 0 at 7 days, 1 at 0 days

                if completion_rate >= 0.9 and days_until > 3:
                    probability = 0.1
                else:
                    probability = min(0.95, (1.0 - completion_rate) * 0.6 + proximity_factor * 0.3)

                if probability < 0.2:
                    continue

                person_display = person_name or f"person_id={pid}" if pid else "unassigned"
                risks.append({
                    "commitment_id": cid,
                    "person_name": person_display,
                    "alert_type": "deadline_risk",
                    "commitment": text[:200],
                    "deadline": str(deadline),
                    "days_remaining": round(days_until, 1),
                    "completion_rate": round(completion_rate, 2),
                    "probability": round(probability, 2),
                    "prediction": (
                        f"Commitment '{text[:80]}...' due in {days_until:.0f} days. "
                        f"{person_display} has {completion_rate*100:.0f}% historical completion rate."
                    ),
                    "suggested_action": f"Follow up with {person_display} on deadline {deadline.strftime('%Y-%m-%d')}",
                })

    log.info("predictive_alerts.deadline_risks", count=len(risks))
    return risks


def _store_alerts(alerts: list[dict[str, Any]]) -> int:
    """Store new alerts in DB. Returns count of new alerts stored."""
    if not alerts:
        return 0

    stored = 0
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for alert in alerts:
                # Skip if very similar alert already active
                cur.execute("""
                    SELECT id FROM predictive_alerts
                    WHERE alert_type = %s
                      AND prediction = %s
                      AND status = 'active'
                      AND created_at > NOW() - INTERVAL '7 days'
                    LIMIT 1
                """, (alert["alert_type"], alert.get("prediction", "")))

                rows = cur.fetchall()
                if rows:
                    continue  # duplicate, skip

                evidence = {k: v for k, v in alert.items()
                            if k not in ("alert_type", "prediction", "probability",
                                         "suggested_action", "time_horizon")}

                cur.execute("""
                    INSERT INTO predictive_alerts
                        (alert_type, prediction, probability, evidence,
                         time_horizon, suggested_action)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    alert["alert_type"],
                    alert.get("prediction", ""),
                    alert.get("probability", 0.5),
                    json.dumps(evidence, default=str),
                    alert.get("time_horizon", "1-2 weeks"),
                    alert.get("suggested_action"),
                ))
                stored += 1

            conn.commit()

    log.info("predictive_alerts.stored", count=stored)
    return stored


def run_predictive_scan() -> dict[str, Any]:
    """Full predictive scan: escalation, communication gaps, deadline risks."""
    _ensure_tables()

    all_alerts = []

    # 1. Communication gaps (no per-person loop needed)
    try:
        gaps = predict_communication_gaps()
        all_alerts.extend(gaps)
    except Exception as e:
        log.error("predictive_alerts.gaps_error", error=str(e))
        gaps = []

    # 2. Deadline risks
    try:
        deadlines = predict_deadline_risks()
        all_alerts.extend(deadlines)
    except Exception as e:
        log.error("predictive_alerts.deadline_error", error=str(e))
        deadlines = []

    # 3. Escalation risk — scan people with recent activity
    escalations = []
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT en.canonical_name
                    FROM entities en
                    JOIN event_entities ee ON ee.entity_id = en.id
                    JOIN events e ON e.id = ee.event_id
                    WHERE en.entity_type = 'person'
                      AND e.event_time > NOW() - INTERVAL '14 days'
                      AND e.event_type IN ('conflict', 'escalation', 'blocker')
                      AND en.canonical_name IS NOT NULL
                      AND en.canonical_name != ''
                """)
                conflict_people = [r[0] for r in cur.fetchall()]

        for person in conflict_people:
            try:
                result = predict_escalation_risk(person)
                if result.get("prediction"):
                    escalations.append(result)
                    all_alerts.append(result)
            except Exception as e:
                log.error("predictive_alerts.escalation_error",
                          person=person, error=str(e))
    except Exception as e:
        log.error("predictive_alerts.escalation_scan_error", error=str(e))

    # Store alerts
    stored = _store_alerts(all_alerts)

    log.info("predictive_alerts.scan_complete",
             escalations=len(escalations), gaps=len(gaps),
             deadlines=len(deadlines), stored=stored)

    return {
        "escalation_risks": escalations,
        "communication_gaps": gaps,
        "deadline_risks": deadlines,
        "total_alerts": len(all_alerts),
        "new_stored": stored,
        "status": "ok",
    }
