"""Helper query functions for the CEO Dashboard views.

Each function queries the corresponding database view and returns
structured dicts ready for API consumption.
"""

from __future__ import annotations

import json

import structlog
from psycopg import Connection

log = structlog.get_logger("ceo_dashboard.queries")


def get_current_health(conn: Connection) -> dict:
    """Get the latest org health snapshot from v_current_org_health.

    Returns:
        Dict with org health data, or empty dict if no snapshot exists.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT snapshot_id, week_start, org_health_score, org_health_label,
                   score_delta_1w, score_delta_4w,
                   prev_week_score, rolling_4w_avg,
                   financial_waste_pln, top_cost_processes, budget_overruns_count,
                   critical_people_at_risk, high_impact_departures, team_instability_score,
                   process_health_avg, critical_processes, processes_improving, processes_declining,
                   top_investment_opps, dept_health_breakdown,
                   critical_alerts, warning_alerts, computed_at
            FROM v_current_org_health
            LIMIT 1
            """
        )
        row = cur.fetchone()

    if not row:
        log.info("no_health_snapshot_available")
        return {}

    return {
        "snapshot_id": str(row[0]),
        "week_start": str(row[1]),
        "org_health_score": int(row[2]),
        "org_health_label": row[3],
        "score_delta_1w": float(row[4]) if row[4] is not None else None,
        "score_delta_4w": float(row[5]) if row[5] is not None else None,
        "prev_week_score": int(row[6]) if row[6] is not None else None,
        "rolling_4w_avg": round(float(row[7]), 1) if row[7] is not None else None,
        "financial_waste_pln": float(row[8]) if row[8] is not None else None,
        "top_cost_processes": row[9] if isinstance(row[9], list) else json.loads(row[9]) if row[9] else [],
        "budget_overruns_count": int(row[10]) if row[10] is not None else 0,
        "critical_people_at_risk": int(row[11]) if row[11] is not None else 0,
        "high_impact_departures": row[12] if isinstance(row[12], list) else json.loads(row[12]) if row[12] else [],
        "team_instability_score": float(row[13]) if row[13] is not None else 0.0,
        "process_health_avg": float(row[14]) if row[14] is not None else 0.0,
        "critical_processes": int(row[15]) if row[15] is not None else 0,
        "processes_improving": int(row[16]) if row[16] is not None else 0,
        "processes_declining": int(row[17]) if row[17] is not None else 0,
        "top_investment_opps": row[18] if isinstance(row[18], list) else json.loads(row[18]) if row[18] else [],
        "dept_health_breakdown": row[19] if isinstance(row[19], dict) else json.loads(row[19]) if row[19] else {},
        "critical_alerts": row[20] if isinstance(row[20], list) else json.loads(row[20]) if row[20] else [],
        "warning_alerts": row[21] if isinstance(row[21], list) else json.loads(row[21]) if row[21] else [],
        "computed_at": str(row[22]) if row[22] else None,
    }


def get_processes_needing_attention(conn: Connection) -> list[dict]:
    """Get processes that need CEO attention from v_process_attention_needed.

    Returns:
        List of dicts with process health and attribution data.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT process_id, process_name, department, process_type,
                   health_score, throughput, overdue_rate, error_rate,
                   rework_rate, escalation_rate, csat_score,
                   direction, severity,
                   attribution_process, attribution_people, attribution_interaction,
                   confidence, narrative, primary_recommendation, recommendation_type,
                   week_start
            FROM v_process_attention_needed
            LIMIT 50
            """
        )
        rows = cur.fetchall()

    results = []
    for r in rows:
        results.append({
            "process_id": str(r[0]),
            "process_name": r[1],
            "department": r[2],
            "process_type": r[3],
            "health_score": float(r[4]) if r[4] is not None else None,
            "throughput": float(r[5]) if r[5] is not None else None,
            "overdue_rate": float(r[6]) if r[6] is not None else None,
            "error_rate": float(r[7]) if r[7] is not None else None,
            "rework_rate": float(r[8]) if r[8] is not None else None,
            "escalation_rate": float(r[9]) if r[9] is not None else None,
            "csat_score": float(r[10]) if r[10] is not None else None,
            "direction": r[11],
            "severity": r[12],
            "attribution_process": float(r[13]) if r[13] is not None else None,
            "attribution_people": float(r[14]) if r[14] is not None else None,
            "attribution_interaction": float(r[15]) if r[15] is not None else None,
            "confidence": float(r[16]) if r[16] is not None else None,
            "narrative": r[17],
            "primary_recommendation": r[18],
            "recommendation_type": r[19],
            "week_start": str(r[20]) if r[20] else None,
        })

    log.info("processes_needing_attention", count=len(results))
    return results


def get_human_risk_map(conn: Connection) -> list[dict]:
    """Get human risk map from v_human_risk_map.

    Returns:
        List of dicts with person flight risk and process impact data.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT person_id, full_name, email,
                   flight_risk_score, delivery_score, evaluated_at,
                   critical_processes, departure_impact_score, process_names
            FROM v_human_risk_map
            LIMIT 50
            """
        )
        rows = cur.fetchall()

    results = []
    for r in rows:
        results.append({
            "person_id": str(r[0]),
            "full_name": r[1],
            "email": r[2],
            "flight_risk_score": float(r[3]) if r[3] is not None else 0.0,
            "delivery_score": float(r[4]) if r[4] is not None else None,
            "evaluated_at": str(r[5]) if r[5] else None,
            "critical_processes": int(r[6]) if r[6] is not None else 0,
            "departure_impact_score": float(r[7]) if r[7] is not None else 0.0,
            "process_names": list(r[8]) if r[8] else [],
        })

    log.info("human_risk_map", count=len(results))
    return results


def get_financial_waste(conn: Connection) -> list[dict]:
    """Get financial waste data from v_financial_waste.

    Returns:
        List of dicts with per-process waste estimates.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT process_id, process_name, department, week_start,
                   cost_per_unit_pln, throughput, overdue_rate, rework_rate,
                   estimated_waste_pln_week,
                   direction, severity,
                   attribution_process, attribution_people,
                   primary_recommendation
            FROM v_financial_waste
            LIMIT 50
            """
        )
        rows = cur.fetchall()

    results = []
    for r in rows:
        results.append({
            "process_id": str(r[0]),
            "process_name": r[1],
            "department": r[2],
            "week_start": str(r[3]) if r[3] else None,
            "cost_per_unit_pln": float(r[4]) if r[4] is not None else 0.0,
            "throughput": float(r[5]) if r[5] is not None else 0.0,
            "overdue_rate": float(r[6]) if r[6] is not None else 0.0,
            "rework_rate": float(r[7]) if r[7] is not None else 0.0,
            "estimated_waste_pln_week": float(r[8]) if r[8] is not None else 0.0,
            "direction": r[9],
            "severity": r[10],
            "attribution_process": float(r[11]) if r[11] is not None else None,
            "attribution_people": float(r[12]) if r[12] is not None else None,
            "primary_recommendation": r[13],
        })

    total = sum(r["estimated_waste_pln_week"] for r in results)
    log.info("financial_waste", count=len(results), total_waste_pln=round(total, 2))
    return results


def get_health_trend(conn: Connection, weeks: int = 12) -> list[dict]:
    """Get org health score trend for the last N weeks.

    Returns:
        List of dicts with week_start and org_health_score, oldest first.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT week_start, org_health_score, org_health_label,
                   financial_waste_pln, critical_people_at_risk,
                   process_health_avg, critical_processes
            FROM org_health_snapshots
            ORDER BY week_start DESC
            LIMIT %s
            """,
            (weeks,),
        )
        rows = cur.fetchall()

    results = [
        {
            "week_start": str(r[0]),
            "org_health_score": int(r[1]),
            "org_health_label": r[2],
            "financial_waste_pln": float(r[3]) if r[3] is not None else None,
            "critical_people_at_risk": int(r[4]) if r[4] is not None else 0,
            "process_health_avg": float(r[5]) if r[5] is not None else None,
            "critical_processes": int(r[6]) if r[6] is not None else 0,
        }
        for r in reversed(rows)  # oldest first
    ]

    log.info("health_trend", weeks_requested=weeks, weeks_returned=len(results))
    return results
