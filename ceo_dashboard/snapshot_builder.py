"""Compute org-wide health snapshot for a given week.

Aggregates financial, process, people, and quality signals into a single
org_health_score (0-100) and UPSERTs into org_health_snapshots.
"""

from __future__ import annotations

import json
from datetime import date

import structlog
from psycopg import Connection

log = structlog.get_logger("ceo_dashboard.snapshot_builder")

# Org health score weights
W_FINANCIAL = 0.30
W_PROCESS = 0.25
W_PEOPLE = 0.25
W_QUALITY = 0.20


def _compute_financial_health(week_start: date, conn: Connection) -> tuple[float, dict]:
    """Compute financial health (0-100) and Q1 data.

    100 - |avg_budget_variance * 100| - waste_penalty
    """
    with conn.cursor() as cur:
        # Budget variance from process_metrics
        cur.execute(
            """
            SELECT AVG(budget_variance), COUNT(*) FILTER (WHERE budget_variance > 0.2)
            FROM process_metrics
            WHERE week_start = %s AND budget_variance IS NOT NULL
            """,
            (week_start,),
        )
        row = cur.fetchone()
        avg_variance = float(row[0]) if row and row[0] is not None else 0.0
        overruns_count = int(row[1]) if row and row[1] is not None else 0

        # Financial waste
        cur.execute(
            """
            SELECT COALESCE(SUM(
                cost_per_unit_pln * throughput * (overdue_rate + rework_rate)
            ), 0)
            FROM process_metrics
            WHERE week_start = %s
              AND cost_per_unit_pln IS NOT NULL
              AND cost_per_unit_pln > 0
            """,
            (week_start,),
        )
        waste_row = cur.fetchone()
        total_waste = float(waste_row[0]) if waste_row and waste_row[0] else 0.0

        # Top cost processes
        cur.execute(
            """
            SELECT p.process_name, pm.cost_per_unit_pln * pm.throughput AS weekly_cost,
                   pm.budget_variance
            FROM process_metrics pm
            JOIN processes p ON p.process_id = pm.process_id
            WHERE pm.week_start = %s
              AND pm.cost_per_unit_pln IS NOT NULL
            ORDER BY weekly_cost DESC NULLS LAST
            LIMIT 5
            """,
            (week_start,),
        )
        top_cost = [
            {"process": r[0], "weekly_cost_pln": round(float(r[1]), 2) if r[1] else 0,
             "budget_variance": round(float(r[2]), 3) if r[2] else 0}
            for r in cur.fetchall()
        ]

    # Waste penalty: 1 point per 10k PLN waste, capped at 30
    waste_penalty = min(total_waste / 10_000, 30)
    variance_penalty = abs(avg_variance) * 100

    score = max(0, min(100, 100 - variance_penalty - waste_penalty))

    q1_data = {
        "financial_waste_pln": round(total_waste, 2),
        "top_cost_processes": top_cost,
        "budget_overruns_count": overruns_count,
    }

    return score, q1_data


def _compute_process_health(week_start: date, conn: Connection) -> tuple[float, dict]:
    """Compute process health (0-100) and Q3 data.

    Weighted average of process health scores by throughput,
    with penalties for critical processes.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pm.health_score, pm.throughput
            FROM process_metrics pm
            WHERE pm.week_start = %s AND pm.health_score IS NOT NULL
            """,
            (week_start,),
        )
        rows = cur.fetchall()

    if not rows:
        return 50.0, {"process_health_avg": 0, "critical_processes": 0,
                       "processes_improving": 0, "processes_declining": 0}

    total_weight = 0.0
    weighted_sum = 0.0
    critical = 0

    for health, throughput in rows:
        h = float(health)
        w = float(throughput) if throughput and throughput > 0 else 1.0
        total_weight += w
        weighted_sum += h * w
        if h < 30:
            critical += 1

    avg_health = weighted_sum / total_weight if total_weight > 0 else 50.0

    # Penalty for critical processes: -5 points each, capped at -25
    penalty = min(critical * 5, 25)
    score = max(0, min(100, avg_health - penalty))

    # Improving / declining from attribution
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE direction = 'success') AS improving,
                COUNT(*) FILTER (WHERE direction = 'problem') AS declining
            FROM attribution_results
            WHERE week_start = %s
            """,
            (week_start,),
        )
        trend_row = cur.fetchone()
        improving = int(trend_row[0]) if trend_row else 0
        declining = int(trend_row[1]) if trend_row else 0

    q3_data = {
        "process_health_avg": round(avg_health, 1),
        "critical_processes": critical,
        "processes_improving": improving,
        "processes_declining": declining,
    }

    return score, q3_data


def _compute_people_health(week_start: date, conn: Connection) -> tuple[float, dict]:
    """Compute people health (0-100) and Q2 data.

    100 * (1 - avg_flight_risk_weighted_by_impact)
    """
    with conn.cursor() as cur:
        # Flight risk weighted by process participation count
        cur.execute(
            """
            SELECT ecs.person_id, p.full_name, ecs.flight_risk_score,
                   COUNT(DISTINCT pp.process_id) AS process_count
            FROM employee_competency_scores ecs
            JOIN persons p ON p.person_id = ecs.person_id
            LEFT JOIN process_participations pp ON pp.person_id = ecs.person_id
            WHERE ecs.evaluated_at = (
                SELECT MAX(e2.evaluated_at) FROM employee_competency_scores e2
                WHERE e2.person_id = ecs.person_id
            )
            GROUP BY ecs.person_id, p.full_name, ecs.flight_risk_score
            """,
        )
        rows = cur.fetchall()

    if not rows:
        return 75.0, {"critical_people_at_risk": 0, "high_impact_departures": [],
                       "team_instability_score": 0.0}

    total_weight = 0.0
    weighted_risk = 0.0
    critical_at_risk = 0
    high_impact = []

    for pid, name, risk, proc_count in rows:
        risk_val = float(risk) if risk else 0.0
        weight = max(int(proc_count) if proc_count else 1, 1)
        total_weight += weight
        weighted_risk += risk_val * weight

        if risk_val > 0.7:
            critical_at_risk += 1
            high_impact.append({
                "person_id": str(pid),
                "name": name,
                "flight_risk": risk_val,
                "processes_affected": weight,
            })

    avg_risk = weighted_risk / total_weight if total_weight > 0 else 0.0
    score = max(0, min(100, 100 * (1 - avg_risk)))

    # Team instability: ratio of high-risk people to total
    instability = critical_at_risk / len(rows) if rows else 0.0

    high_impact.sort(key=lambda x: x["flight_risk"], reverse=True)

    q2_data = {
        "critical_people_at_risk": critical_at_risk,
        "high_impact_departures": high_impact[:5],
        "team_instability_score": round(instability, 3),
    }

    return score, q2_data


def _compute_quality_health(week_start: date, conn: Connection) -> float:
    """Compute quality health (0-100).

    Composite of error_rate, csat, change_failure_rate by process type.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                AVG(CASE WHEN error_rate IS NOT NULL THEN 1 - error_rate ELSE NULL END) AS avg_quality,
                AVG(csat_score) / 5.0 AS avg_csat_norm,
                AVG(CASE WHEN rework_rate IS NOT NULL THEN 1 - rework_rate ELSE NULL END) AS avg_no_rework
            FROM process_metrics
            WHERE week_start = %s
            """,
            (week_start,),
        )
        row = cur.fetchone()

    if not row or all(v is None for v in row):
        return 60.0

    quality = float(row[0]) if row[0] is not None else 0.7
    csat = float(row[1]) if row[1] is not None else 0.7
    no_rework = float(row[2]) if row[2] is not None else 0.8

    score = (quality * 0.4 + csat * 0.3 + no_rework * 0.3) * 100
    return max(0, min(100, score))


def _compute_dept_breakdown(week_start: date, conn: Connection) -> dict:
    """Compute health breakdown per department."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.department,
                   AVG(pm.health_score) AS avg_health,
                   COUNT(*) AS process_count,
                   COUNT(*) FILTER (WHERE pm.health_score < 30) AS critical
            FROM process_metrics pm
            JOIN processes p ON p.process_id = pm.process_id
            WHERE pm.week_start = %s AND p.department IS NOT NULL
            GROUP BY p.department
            ORDER BY avg_health ASC
            """,
            (week_start,),
        )
        rows = cur.fetchall()

    breakdown = {}
    for dept, avg_h, count, crit in rows:
        breakdown[dept] = {
            "avg_health": round(float(avg_h), 1) if avg_h else 0,
            "process_count": int(count),
            "critical_processes": int(crit) if crit else 0,
        }

    return breakdown


def _label_for_score(score: int) -> str:
    """Map org health score to label."""
    if score >= 80:
        return "excellent"
    if score >= 65:
        return "good"
    if score >= 50:
        return "fair"
    if score >= 35:
        return "at_risk"
    return "critical"


def _compute_deltas(week_start: date, current_score: int, conn: Connection) -> tuple[float | None, float | None]:
    """Compute 1-week and 4-week score deltas."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT week_start, org_health_score
            FROM org_health_snapshots
            WHERE week_start < %s
            ORDER BY week_start DESC
            LIMIT 4
            """,
            (week_start,),
        )
        rows = cur.fetchall()

    if not rows:
        return None, None

    delta_1w = current_score - int(rows[0][1])

    if len(rows) >= 4:
        delta_4w = current_score - int(rows[3][1])
    else:
        delta_4w = None

    return float(delta_1w), float(delta_4w) if delta_4w is not None else None


def compute_org_health_snapshot(
    week_start: date,
    conn: Connection,
) -> dict:
    """Compute and persist an org health snapshot for the given week.

    Calculates 4 health dimensions (financial, process, people, quality),
    computes a weighted org_health_score, and UPSERTs into org_health_snapshots.

    Returns:
        Dict with all snapshot fields.
    """
    log.info("computing_org_health", week_start=str(week_start))

    # Import alert engine
    from .alert_engine import generate_alerts

    # Compute 4 dimensions
    financial_score, q1_data = _compute_financial_health(week_start, conn)
    process_score, q3_data = _compute_process_health(week_start, conn)
    people_score, q2_data = _compute_people_health(week_start, conn)
    quality_score = _compute_quality_health(week_start, conn)

    # Weighted composite
    org_score = int(round(
        W_FINANCIAL * financial_score
        + W_PROCESS * process_score
        + W_PEOPLE * people_score
        + W_QUALITY * quality_score
    ))
    org_score = max(0, min(100, org_score))
    org_label = _label_for_score(org_score)

    # Deltas
    delta_1w, delta_4w = _compute_deltas(week_start, org_score, conn)

    # Department breakdown
    dept_breakdown = _compute_dept_breakdown(week_start, conn)

    # Investment opportunities (Q4): top processes with success attribution
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.process_name, ar.attribution_process, pm.health_score, pm.throughput
            FROM attribution_results ar
            JOIN processes p ON p.process_id = ar.process_id
            LEFT JOIN process_metrics pm ON pm.process_id = ar.process_id
                AND pm.week_start = ar.week_start
            WHERE ar.week_start = %s AND ar.direction = 'success'
            ORDER BY pm.health_score DESC NULLS LAST
            LIMIT 5
            """,
            (week_start,),
        )
        investment_rows = cur.fetchall()

    top_investment = [
        {"process": r[0], "health": float(r[2]) if r[2] else None,
         "throughput": float(r[3]) if r[3] else None}
        for r in investment_rows
    ]

    # Build snapshot dict
    snapshot = {
        "week_start": str(week_start),
        "org_health_score": org_score,
        "org_health_label": org_label,
        "score_delta_1w": delta_1w,
        "score_delta_4w": delta_4w,
        # Q1
        "financial_waste_pln": q1_data["financial_waste_pln"],
        "top_cost_processes": q1_data["top_cost_processes"],
        "budget_overruns_count": q1_data["budget_overruns_count"],
        # Q2
        "critical_people_at_risk": q2_data["critical_people_at_risk"],
        "high_impact_departures": q2_data["high_impact_departures"],
        "team_instability_score": q2_data["team_instability_score"],
        # Q3
        "process_health_avg": q3_data["process_health_avg"],
        "critical_processes": q3_data["critical_processes"],
        "processes_improving": q3_data["processes_improving"],
        "processes_declining": q3_data["processes_declining"],
        # Q4
        "top_investment_opps": top_investment,
        # Breakdown
        "dept_health_breakdown": dept_breakdown,
    }

    # Generate alerts
    critical_alerts, warning_alerts = generate_alerts(snapshot, conn)
    snapshot["critical_alerts"] = critical_alerts
    snapshot["warning_alerts"] = warning_alerts

    # UPSERT into database
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO org_health_snapshots (
                week_start, org_health_score, org_health_label,
                score_delta_1w, score_delta_4w,
                financial_waste_pln, top_cost_processes, budget_overruns_count,
                critical_people_at_risk, high_impact_departures, team_instability_score,
                process_health_avg, critical_processes, processes_improving, processes_declining,
                top_investment_opps,
                dept_health_breakdown, critical_alerts, warning_alerts
            ) VALUES (
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, %s, %s
            )
            ON CONFLICT (week_start) DO UPDATE SET
                org_health_score = EXCLUDED.org_health_score,
                org_health_label = EXCLUDED.org_health_label,
                score_delta_1w = EXCLUDED.score_delta_1w,
                score_delta_4w = EXCLUDED.score_delta_4w,
                financial_waste_pln = EXCLUDED.financial_waste_pln,
                top_cost_processes = EXCLUDED.top_cost_processes,
                budget_overruns_count = EXCLUDED.budget_overruns_count,
                critical_people_at_risk = EXCLUDED.critical_people_at_risk,
                high_impact_departures = EXCLUDED.high_impact_departures,
                team_instability_score = EXCLUDED.team_instability_score,
                process_health_avg = EXCLUDED.process_health_avg,
                critical_processes = EXCLUDED.critical_processes,
                processes_improving = EXCLUDED.processes_improving,
                processes_declining = EXCLUDED.processes_declining,
                top_investment_opps = EXCLUDED.top_investment_opps,
                dept_health_breakdown = EXCLUDED.dept_health_breakdown,
                critical_alerts = EXCLUDED.critical_alerts,
                warning_alerts = EXCLUDED.warning_alerts,
                computed_at = now()
            """,
            (
                week_start, org_score, org_label,
                delta_1w, delta_4w,
                q1_data["financial_waste_pln"],
                json.dumps(q1_data["top_cost_processes"], default=str),
                q1_data["budget_overruns_count"],
                q2_data["critical_people_at_risk"],
                json.dumps(q2_data["high_impact_departures"], default=str),
                q2_data["team_instability_score"],
                q3_data["process_health_avg"],
                q3_data["critical_processes"],
                q3_data["processes_improving"],
                q3_data["processes_declining"],
                json.dumps(top_investment, default=str),
                json.dumps(dept_breakdown, default=str),
                json.dumps(critical_alerts, default=str),
                json.dumps(warning_alerts, default=str),
            ),
        )
    conn.commit()

    log.info(
        "org_health_computed",
        week_start=str(week_start),
        score=org_score,
        label=org_label,
        critical_alerts=len(critical_alerts),
        warning_alerts=len(warning_alerts),
    )

    return snapshot
