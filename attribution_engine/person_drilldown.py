"""Person-level drilldown: contribution analysis across all processes.

For a specific person, calculates their contribution score per process
using a weighted composite of overdue rate, flight risk, delivery score,
and escalation rate.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import structlog
from psycopg import Connection

log = structlog.get_logger("attribution_engine.person_drilldown")

# Contribution score weights
W_OVERDUE = 0.35
W_FLIGHT_RISK = 0.25
W_DELIVERY = 0.20
W_ESCALATION = 0.20


def drilldown_person(
    person_id: UUID,
    week_start: date,
    conn: Connection,
) -> dict:
    """Analyze a person's contribution across all their processes.

    Contribution score per process = weighted sum of:
    - tasks_overdue_owned / tasks_owned (0.35) -- higher = worse
    - flight_risk (0.25) -- higher = worse
    - 1 - delivery_score/5 (0.20) -- lower delivery = worse
    - escalations_caused / participation (0.20) -- higher = worse

    Returns:
        Dict with person info, per-process contributions,
        top_people_positive and top_people_negative lists.
    """
    log.info("person_drilldown", person_id=str(person_id), week_start=str(week_start))

    # Get person info
    with conn.cursor() as cur:
        cur.execute(
            "SELECT person_id, full_name, email FROM persons WHERE person_id = %s",
            (str(person_id),),
        )
        person_row = cur.fetchone()

    if not person_row:
        log.warning("person_not_found", person_id=str(person_id))
        return {"error": "person_not_found", "person_id": str(person_id)}

    person_name = person_row[1]
    person_email = person_row[2]

    # Get flight risk from latest competency eval
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
            (str(person_id),),
        )
        comp_row = cur.fetchone()
        if comp_row:
            flight_risk = float(comp_row[0] or 0.0)
            delivery_score = float(comp_row[1] or 3.0)

    # Get all process participations
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pp.process_id, p.process_name, p.department,
                   pp.role, pp.tasks_owned, pp.tasks_overdue, pp.escalations_caused,
                   pm.health_score, pm.throughput
            FROM process_participations pp
            JOIN processes p ON p.process_id = pp.process_id
            LEFT JOIN process_metrics pm ON pm.process_id = pp.process_id
                AND pm.week_start = (
                    SELECT MAX(week_start) FROM process_metrics
                    WHERE process_id = pp.process_id AND week_start <= %s
                )
            WHERE pp.person_id = %s
            """,
            (week_start, str(person_id)),
        )
        participations = cur.fetchall()

    if not participations:
        return {
            "person_id": str(person_id),
            "person_name": person_name,
            "email": person_email,
            "flight_risk": flight_risk,
            "delivery_score": delivery_score,
            "processes": [],
            "top_people_positive": [],
            "top_people_negative": [],
            "overall_contribution": 0.0,
        }

    process_contributions = []

    for row in participations:
        (proc_id, proc_name, department, role,
         tasks_owned, tasks_overdue, escalations_caused,
         health_score, throughput) = row

        tasks_owned = tasks_owned or 0
        tasks_overdue = tasks_overdue or 0
        escalations_caused = escalations_caused or 0

        # Calculate overdue ratio
        overdue_ratio = (tasks_overdue / tasks_owned) if tasks_owned > 0 else 0.0

        # Calculate escalation ratio
        escalation_ratio = (escalations_caused / max(tasks_owned, 1))

        # Contribution score: higher = MORE problematic
        problem_score = (
            W_OVERDUE * overdue_ratio
            + W_FLIGHT_RISK * flight_risk
            + W_DELIVERY * (1 - delivery_score / 5.0)
            + W_ESCALATION * escalation_ratio
        )

        # Invert: 1 - problem_score = positive contribution
        contribution = round(1.0 - problem_score, 3)

        process_contributions.append({
            "process_id": str(proc_id),
            "process_name": proc_name,
            "department": department,
            "role": role,
            "tasks_owned": tasks_owned,
            "tasks_overdue": tasks_overdue,
            "overdue_ratio": round(overdue_ratio, 3),
            "escalations_caused": escalations_caused,
            "escalation_ratio": round(escalation_ratio, 3),
            "process_health": float(health_score) if health_score is not None else None,
            "throughput": float(throughput) if throughput is not None else None,
            "contribution_score": contribution,
            "problem_score": round(problem_score, 3),
        })

    process_contributions.sort(key=lambda x: x["contribution_score"])

    # Overall contribution = weighted avg by throughput
    total_weight = 0.0
    weighted_contribution = 0.0
    for pc in process_contributions:
        w = pc["throughput"] if pc["throughput"] and pc["throughput"] > 0 else 1.0
        total_weight += w
        weighted_contribution += pc["contribution_score"] * w

    overall = round(weighted_contribution / total_weight, 3) if total_weight > 0 else 0.5

    # Classify as positive/negative
    positive_processes = [pc for pc in process_contributions if pc["contribution_score"] >= 0.6]
    negative_processes = [pc for pc in process_contributions if pc["contribution_score"] < 0.4]

    result = {
        "person_id": str(person_id),
        "person_name": person_name,
        "email": person_email,
        "flight_risk": flight_risk,
        "delivery_score": delivery_score,
        "overall_contribution": overall,
        "processes": process_contributions,
        "top_people_positive": [
            {
                "process_name": pc["process_name"],
                "process_id": pc["process_id"],
                "contribution_score": pc["contribution_score"],
            }
            for pc in positive_processes[:5]
        ],
        "top_people_negative": [
            {
                "process_name": pc["process_name"],
                "process_id": pc["process_id"],
                "contribution_score": pc["contribution_score"],
                "problem_score": pc["problem_score"],
            }
            for pc in negative_processes[:5]
        ],
    }

    log.info(
        "person_drilldown_complete",
        person_id=str(person_id),
        process_count=len(process_contributions),
        overall_contribution=overall,
    )

    return result
