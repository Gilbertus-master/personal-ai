"""Correlate people and process signals for attribution analysis.

Pulls signals from employee_competency_scores, person_open_loops,
person_behavioral, process_metrics, and process_participations to build
a structured signal dict for the attribution scorer.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import structlog
from psycopg import Connection

log = structlog.get_logger("attribution_engine.correlator")


def _fetch_people_signals(process_id: UUID, week_start: date, conn: Connection) -> dict:
    """Pull people-level signals for all participants in a process."""
    with conn.cursor() as cur:
        # Get participants
        cur.execute(
            """
            SELECT pp.person_id, p.full_name, pp.role, pp.tasks_owned, pp.tasks_overdue
            FROM process_participations pp
            JOIN persons p ON p.person_id = pp.person_id
            WHERE pp.process_id = %s
            """,
            (str(process_id),),
        )
        participants = cur.fetchall()

    if not participants:
        return {"participants": [], "avg_flight_risk": 0.0, "avg_delivery_score": 0.0,
                "avg_open_loops": 0.0, "trajectory_signals": []}

    participant_data = []

    for row in participants:
        pid, name, role, tasks_owned, tasks_overdue = row
        pid_str = str(pid)

        # Flight risk and delivery score from employee_competency_scores
        flight_risk = 0.0
        delivery_score = 3.0
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT flight_risk_score, overall_score
                FROM employee_competency_scores
                WHERE person_id = %s
                ORDER BY evaluated_at DESC
                LIMIT 1
                """,
                (pid_str,),
            )
            comp_row = cur.fetchone()
            if comp_row:
                flight_risk = float(comp_row[0] or 0.0)
                delivery_score = float(comp_row[1] or 3.0)

        # Open loops count
        open_loops_count = 0
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM person_open_loops
                WHERE person_id = %s AND status = 'open'
                """,
                (pid_str,),
            )
            ol_row = cur.fetchone()
            if ol_row:
                open_loops_count = int(ol_row[0])

        # Relationship trajectory
        trajectory = "stable"
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT trajectory
                FROM person_behavioral
                WHERE person_id = %s
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (pid_str,),
            )
            traj_row = cur.fetchone()
            if traj_row and traj_row[0]:
                trajectory = str(traj_row[0])

        overdue_ratio = (tasks_overdue / tasks_owned) if tasks_owned and tasks_owned > 0 else 0.0

        participant_data.append({
            "person_id": pid_str,
            "person_name": name,
            "role": role,
            "tasks_owned": tasks_owned or 0,
            "tasks_overdue": tasks_overdue or 0,
            "overdue_ratio": round(overdue_ratio, 3),
            "flight_risk": flight_risk,
            "delivery_score": delivery_score,
            "open_loops_count": open_loops_count,
            "trajectory": trajectory,
        })

    # Aggregate
    flight_risks = [p["flight_risk"] for p in participant_data if p["flight_risk"] > 0]
    delivery_scores = [p["delivery_score"] for p in participant_data if p["delivery_score"] > 0]
    open_loops_all = [p["open_loops_count"] for p in participant_data]
    trajectories_cooling = [p for p in participant_data if p["trajectory"] in ("cooling", "declining")]

    avg_flight_risk = sum(flight_risks) / len(flight_risks) if flight_risks else 0.0
    avg_delivery = sum(delivery_scores) / len(delivery_scores) if delivery_scores else 3.0
    avg_open_loops = sum(open_loops_all) / len(open_loops_all) if open_loops_all else 0.0

    return {
        "participants": participant_data,
        "avg_flight_risk": round(avg_flight_risk, 3),
        "avg_delivery_score": round(avg_delivery, 2),
        "avg_open_loops": round(avg_open_loops, 1),
        "trajectory_signals": [
            {"person_id": p["person_id"], "person_name": p["person_name"], "trajectory": p["trajectory"]}
            for p in trajectories_cooling
        ],
    }


def _fetch_process_signals(process_id: UUID, week_start: date, conn: Connection) -> dict:
    """Pull process-level signals: health score, anomaly flags, recent trend."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT week_start, health_score, throughput, avg_cycle_time_hours,
                   overdue_rate, error_rate, rework_rate, escalation_rate, csat_score
            FROM process_metrics
            WHERE process_id = %s
            ORDER BY week_start DESC
            LIMIT 9
            """,
            (str(process_id),),
        )
        rows = cur.fetchall()

    if not rows:
        return {
            "current_health": None,
            "baseline_health": None,
            "weeks_data": 0,
            "health_trend": [],
            "metrics": {},
        }

    current = rows[0]
    baseline_scores = [float(r[1]) for r in rows[1:] if r[1] is not None]
    baseline_health = sum(baseline_scores) / len(baseline_scores) if baseline_scores else None

    health_trend = [
        {"week": str(r[0]), "health": float(r[1]) if r[1] is not None else None}
        for r in reversed(rows)
    ]

    return {
        "current_health": float(current[1]) if current[1] is not None else None,
        "baseline_health": round(baseline_health, 1) if baseline_health is not None else None,
        "weeks_data": len(rows),
        "health_trend": health_trend,
        "metrics": {
            "throughput": float(current[2]) if current[2] is not None else None,
            "avg_cycle_time_hours": float(current[3]) if current[3] is not None else None,
            "overdue_rate": float(current[4]) if current[4] is not None else None,
            "error_rate": float(current[5]) if current[5] is not None else None,
            "rework_rate": float(current[6]) if current[6] is not None else None,
            "escalation_rate": float(current[7]) if current[7] is not None else None,
            "csat_score": float(current[8]) if current[8] is not None else None,
        },
    }


def correlate_people_process(
    process_id: UUID,
    week_start: date,
    conn: Connection,
) -> dict:
    """Correlate people and process signals for a given process and week.

    Returns:
        Dict with keys 'people_signals' and 'process_signals'.
    """
    log.info("correlating_signals", process_id=str(process_id), week_start=str(week_start))

    people_signals = _fetch_people_signals(process_id, week_start, conn)
    process_signals = _fetch_process_signals(process_id, week_start, conn)

    log.info(
        "correlation_complete",
        process_id=str(process_id),
        participants=len(people_signals["participants"]),
        weeks_data=process_signals["weeks_data"],
    )

    return {
        "people_signals": people_signals,
        "process_signals": process_signals,
    }
