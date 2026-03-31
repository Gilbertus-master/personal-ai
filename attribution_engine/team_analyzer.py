"""Team-level aggregation of attribution results.

Aggregates attribution_results for all processes owned by a team,
computes team health, identifies top problems and performers.
"""

from __future__ import annotations

from datetime import date

import structlog
from psycopg import Connection

from .models import PersonContribution, TeamAnalysis

log = structlog.get_logger("attribution_engine.team_analyzer")


def analyze_team(
    team_id: str,
    week_start: date,
    conn: Connection,
) -> TeamAnalysis:
    """Aggregate attribution results for all processes belonging to a team.

    Args:
        team_id: Team/department identifier.
        week_start: Monday of the analysis week.
        conn: Active DB connection.

    Returns:
        TeamAnalysis with aggregated metrics.
    """
    log.info("analyzing_team", team_id=team_id, week_start=str(week_start))

    # Fetch all attribution results for this team's processes this week
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ar.process_id, ar.direction, ar.severity,
                   ar.attribution_process, ar.attribution_people,
                   ar.attribution_interaction, ar.confidence,
                   ar.top_people_positive, ar.top_people_negative,
                   ar.narrative, ar.primary_recommendation,
                   pm.health_score, pm.throughput,
                   p.process_name
            FROM attribution_results ar
            JOIN processes p ON p.process_id = ar.process_id
            LEFT JOIN process_metrics pm ON pm.process_id = ar.process_id
                AND pm.week_start = ar.week_start
            WHERE ar.team_id = %s
              AND ar.week_start = %s
            """,
            (team_id, week_start),
        )
        rows = cur.fetchall()

    if not rows:
        log.info("no_attribution_data_for_team", team_id=team_id)
        return TeamAnalysis(
            team_id=team_id,
            week_start=week_start,
        )

    # Compute team health as weighted average of process health scores by throughput
    total_weight = 0.0
    weighted_health_sum = 0.0
    top_problems = []
    process_count = len(rows)

    for row in rows:
        (process_id, direction, severity,
         attr_process, attr_people, attr_interaction, confidence,
         top_pos, top_neg, narrative, recommendation,
         health_score, throughput, process_name) = row

        weight = float(throughput) if throughput and throughput > 0 else 1.0
        health = float(health_score) if health_score is not None else 50.0

        total_weight += weight
        weighted_health_sum += health * weight

        if direction == "problem":
            top_problems.append({
                "process_id": str(process_id),
                "process_name": process_name,
                "health_score": health,
                "severity": severity,
                "attribution_process": float(attr_process) if attr_process else 0.0,
                "attribution_people": float(attr_people) if attr_people else 0.0,
                "recommendation": recommendation,
            })

    team_health = weighted_health_sum / total_weight if total_weight > 0 else 50.0
    top_problems.sort(key=lambda x: x["health_score"])

    # Aggregate people contributions across all team processes
    person_scores: dict[str, dict] = {}
    for row in rows:
        top_pos = row[7] or []
        top_neg = row[8] or []

        for p in top_pos:
            pid = p.get("person_id", "")
            if pid not in person_scores:
                person_scores[pid] = {
                    "person_id": pid,
                    "person_name": p.get("person_name", ""),
                    "impact_scores": [],
                    "flight_risk": p.get("flight_risk", 0.0),
                    "delivery_score": p.get("delivery_score", 3.0),
                }
            person_scores[pid]["impact_scores"].append(p.get("impact_score", 0.5))

        for p in top_neg:
            pid = p.get("person_id", "")
            if pid not in person_scores:
                person_scores[pid] = {
                    "person_id": pid,
                    "person_name": p.get("person_name", ""),
                    "impact_scores": [],
                    "flight_risk": p.get("flight_risk", 0.0),
                    "delivery_score": p.get("delivery_score", 3.0),
                }
            person_scores[pid]["impact_scores"].append(p.get("impact_score", 0.5))

    # Convert to PersonContribution
    all_contributions = []
    for pid, data in person_scores.items():
        scores = data["impact_scores"]
        avg_score = sum(scores) / len(scores) if scores else 0.5
        # Normalize to [-1, 1] range: 0.5 is neutral, >0.6 positive, <0.4 negative
        contribution_score = round((avg_score - 0.5) * 2, 3)
        all_contributions.append(PersonContribution(
            person_id=pid,
            person_name=data["person_name"],
            contribution_score=max(-1.0, min(1.0, contribution_score)),
            flight_risk=data["flight_risk"],
            delivery_score=data["delivery_score"],
        ))

    all_contributions.sort(key=lambda x: x.contribution_score, reverse=True)
    top_performers = [c for c in all_contributions if c.contribution_score > 0][:5]
    worst_performers = [c for c in all_contributions if c.contribution_score < 0][:5]

    analysis = TeamAnalysis(
        team_id=team_id,
        week_start=week_start,
        team_health=round(team_health, 1),
        process_count=process_count,
        top_problems=top_problems[:5],
        top_performers=top_performers,
        worst_performers=worst_performers,
    )

    log.info(
        "team_analysis_complete",
        team_id=team_id,
        team_health=analysis.team_health,
        process_count=process_count,
        problems=len(top_problems),
    )

    return analysis
