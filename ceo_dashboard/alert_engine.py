"""Alert engine for CEO dashboard.

Generates critical and warning alerts based on org health snapshot data
and current process/people signals.
"""

from __future__ import annotations

import structlog
from psycopg import Connection

log = structlog.get_logger("ceo_dashboard.alert_engine")


def generate_alerts(
    snapshot: dict,
    conn: Connection,
) -> tuple[list[dict], list[dict]]:
    """Generate critical and warning alerts from snapshot data.

    Critical triggers:
    - org_health < 35
    - any process health < 25
    - flight_risk > 0.8 for key person
    - budget_variance > 20%

    Warning triggers:
    - org_health < 50
    - process declining 3+ weeks
    - new high flight_risk (> 0.6)
    - sustained_decline anomaly

    Returns:
        Tuple of (critical_alerts, warning_alerts).
    """
    critical: list[dict] = []
    warning: list[dict] = []

    org_score = snapshot.get("org_health_score", 100)

    # --- CRITICAL ALERTS ---

    # C1: Org health critical
    if org_score < 35:
        critical.append({
            "type": "org_health_critical",
            "message": f"Zdrowie organizacji na poziomie krytycznym: {org_score}/100",
            "affected_entity": "organization",
            "severity": "critical",
            "suggested_action": "Natychmiastowy przeglad procesow krytycznych i spotkanie zarzadu",
        })

    # C2: Process health < 25
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.process_name, pm.health_score, p.department
            FROM process_metrics pm
            JOIN processes p ON p.process_id = pm.process_id
            WHERE pm.health_score < 25
              AND pm.week_start = (
                  SELECT MAX(week_start) FROM process_metrics
                  WHERE process_id = pm.process_id
              )
            ORDER BY pm.health_score ASC
            """,
        )
        critical_processes = cur.fetchall()

    for proc_name, health, dept in critical_processes:
        critical.append({
            "type": "process_critical",
            "message": f"Proces '{proc_name}' ({dept}) — health={int(health)}/100, wymaga natychmiastowej interwencji",
            "affected_entity": proc_name,
            "severity": "critical",
            "suggested_action": f"Analiza root cause procesu '{proc_name}' i plan naprawczy w 48h",
        })

    # C3: Flight risk > 0.8 for key person (involved in 2+ processes)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.full_name, ecs.flight_risk_score,
                   COUNT(DISTINCT pp.process_id) AS proc_count
            FROM employee_competency_scores ecs
            JOIN persons p ON p.person_id = ecs.person_id
            JOIN process_participations pp ON pp.person_id = ecs.person_id
            WHERE ecs.flight_risk_score > 0.8
              AND ecs.evaluated_at = (
                  SELECT MAX(e2.evaluated_at) FROM employee_competency_scores e2
                  WHERE e2.person_id = ecs.person_id
              )
            GROUP BY p.full_name, ecs.flight_risk_score
            HAVING COUNT(DISTINCT pp.process_id) >= 2
            ORDER BY ecs.flight_risk_score DESC
            """,
        )
        high_risk_people = cur.fetchall()

    for name, risk, proc_count in high_risk_people:
        critical.append({
            "type": "flight_risk_critical",
            "message": f"{name}: flight_risk={risk:.0%}, zaangazowany w {proc_count} procesow",
            "affected_entity": name,
            "severity": "critical",
            "suggested_action": f"Pilna rozmowa retencyjna z {name}, plan sukcesji",
        })

    # C4: Budget overruns > 20%
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.process_name, pm.budget_variance, p.department
            FROM process_metrics pm
            JOIN processes p ON p.process_id = pm.process_id
            WHERE pm.budget_variance > 0.2
              AND pm.week_start = (
                  SELECT MAX(week_start) FROM process_metrics
                  WHERE process_id = pm.process_id
              )
            ORDER BY pm.budget_variance DESC
            """,
        )
        overruns = cur.fetchall()

    for proc_name, variance, dept in overruns:
        critical.append({
            "type": "budget_overrun",
            "message": f"Przekroczenie budzetu procesu '{proc_name}' ({dept}): {float(variance):.0%}",
            "affected_entity": proc_name,
            "severity": "critical",
            "suggested_action": f"Przeglad kosztow procesu '{proc_name}', identyfikacja zrodel przekroczenia",
        })

    # --- WARNING ALERTS ---

    # W1: Org health below 50 but above 35
    if 35 <= org_score < 50:
        warning.append({
            "type": "org_health_warning",
            "message": f"Zdrowie organizacji ponizej normy: {org_score}/100",
            "affected_entity": "organization",
            "severity": "warning",
            "suggested_action": "Przeglad procesow z najnizszym zdrowiem i plan korekcyjny",
        })

    # W2: Processes declining 3+ weeks (from attribution_results)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.process_name, COUNT(*) AS decline_weeks
            FROM attribution_results ar
            JOIN processes p ON p.process_id = ar.process_id
            WHERE ar.direction = 'problem'
            GROUP BY p.process_name
            HAVING COUNT(*) >= 3
            ORDER BY decline_weeks DESC
            """,
        )
        declining = cur.fetchall()

    for proc_name, weeks in declining:
        warning.append({
            "type": "sustained_decline",
            "message": f"Proces '{proc_name}' w trendzie spadkowym od {int(weeks)} tygodni",
            "affected_entity": proc_name,
            "severity": "warning",
            "suggested_action": f"Analiza przyczyn spadku w '{proc_name}', rozwazyc interwencje",
        })

    # W3: New high flight risk (> 0.6, < 0.8 — not already critical)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.full_name, ecs.flight_risk_score,
                   COUNT(DISTINCT pp.process_id) AS proc_count
            FROM employee_competency_scores ecs
            JOIN persons p ON p.person_id = ecs.person_id
            LEFT JOIN process_participations pp ON pp.person_id = ecs.person_id
            WHERE ecs.flight_risk_score > 0.6
              AND ecs.flight_risk_score <= 0.8
              AND ecs.evaluated_at = (
                  SELECT MAX(e2.evaluated_at) FROM employee_competency_scores e2
                  WHERE e2.person_id = ecs.person_id
              )
            GROUP BY p.full_name, ecs.flight_risk_score
            ORDER BY ecs.flight_risk_score DESC
            """,
        )
        moderate_risk = cur.fetchall()

    for name, risk, proc_count in moderate_risk:
        warning.append({
            "type": "flight_risk_elevated",
            "message": f"{name}: flight_risk={risk:.0%}, {proc_count or 0} procesow",
            "affected_entity": name,
            "severity": "warning",
            "suggested_action": f"Monitorowac {name}, rozwazyc rozmowe rozwojowa",
        })

    # W4: Sustained decline anomaly type in latest attribution
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.process_name, ar.interaction_signals
            FROM attribution_results ar
            JOIN processes p ON p.process_id = ar.process_id
            WHERE ar.week_start = (SELECT MAX(week_start) FROM attribution_results)
            """,
        )
        attr_rows = cur.fetchall()

    for proc_name, interaction_signals in attr_rows:
        if not interaction_signals:
            continue
        anomalies = interaction_signals.get("anomalies", []) if isinstance(interaction_signals, dict) else []
        for anomaly in anomalies:
            if isinstance(anomaly, dict) and anomaly.get("anomaly_type") == "sustained_decline":
                metric = anomaly.get("metric_name", "unknown")
                weeks_dec = anomaly.get("weeks_declining", 0)
                if weeks_dec >= 3:
                    warning.append({
                        "type": "sustained_metric_decline",
                        "message": f"'{proc_name}': metryka '{metric}' spada od {weeks_dec} tygodni",
                        "affected_entity": proc_name,
                        "severity": "warning",
                        "suggested_action": f"Zbadac przyczyne spadku '{metric}' w procesie '{proc_name}'",
                    })

    log.info(
        "alerts_generated",
        critical_count=len(critical),
        warning_count=len(warning),
    )

    return critical, warning
