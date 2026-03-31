-- CEO Dashboard views
-- Run: psql -U gilbertus -d gilbertus -f 001_dashboard_views.sql
-- Depends on: attribution_engine/migrations/001_attribution_tables.sql

BEGIN;

-- V1: Current org health with previous week and rolling 4-week average
CREATE OR REPLACE VIEW v_current_org_health AS
SELECT
    ohs.snapshot_id,
    ohs.week_start,
    ohs.org_health_score,
    ohs.org_health_label,
    ohs.score_delta_1w,
    ohs.score_delta_4w,
    LAG(ohs.org_health_score) OVER (ORDER BY ohs.week_start) AS prev_week_score,
    AVG(ohs.org_health_score) OVER (
        ORDER BY ohs.week_start
        ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
    ) AS rolling_4w_avg,
    ohs.financial_waste_pln,
    ohs.top_cost_processes,
    ohs.budget_overruns_count,
    ohs.critical_people_at_risk,
    ohs.high_impact_departures,
    ohs.team_instability_score,
    ohs.process_health_avg,
    ohs.critical_processes,
    ohs.processes_improving,
    ohs.processes_declining,
    ohs.top_investment_opps,
    ohs.dept_health_breakdown,
    ohs.critical_alerts,
    ohs.warning_alerts,
    ohs.computed_at
FROM org_health_snapshots ohs
ORDER BY ohs.week_start DESC;


-- V2: Processes needing attention (health<60 OR severity critical/high)
CREATE OR REPLACE VIEW v_process_attention_needed AS
SELECT
    p.process_id,
    p.process_name,
    p.department,
    p.process_type,
    pm.health_score,
    pm.throughput,
    pm.overdue_rate,
    pm.error_rate,
    pm.rework_rate,
    pm.escalation_rate,
    pm.csat_score,
    ar.direction,
    ar.severity,
    ar.attribution_process,
    ar.attribution_people,
    ar.attribution_interaction,
    ar.confidence,
    ar.narrative,
    ar.primary_recommendation,
    ar.recommendation_type,
    ar.week_start
FROM processes p
JOIN process_metrics pm ON pm.process_id = p.process_id
    AND pm.week_start = (
        SELECT MAX(pm2.week_start) FROM process_metrics pm2
        WHERE pm2.process_id = p.process_id
    )
LEFT JOIN attribution_results ar ON ar.process_id = p.process_id
    AND ar.week_start = pm.week_start
WHERE pm.health_score < 60
   OR ar.severity IN ('critical', 'high')
ORDER BY
    CASE ar.severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
        ELSE 5
    END,
    pm.health_score ASC NULLS LAST;


-- V3: Human risk map — persons with flight_risk > 0.5 and their process impact
CREATE OR REPLACE VIEW v_human_risk_map AS
SELECT
    p.person_id,
    p.full_name,
    p.email,
    ecs.flight_risk_score,
    ecs.overall_score AS delivery_score,
    ecs.evaluated_at,
    COUNT(DISTINCT pp.process_id) AS critical_processes,
    -- Departure impact: flight_risk * number of critical processes * avg inverse health
    ROUND(
        (ecs.flight_risk_score * COUNT(DISTINCT pp.process_id) *
         COALESCE(AVG(CASE WHEN pm.health_score < 60 THEN (100 - pm.health_score) / 100.0 ELSE 0.1 END), 0.1)
        )::numeric, 3
    ) AS departure_impact_score,
    ARRAY_AGG(DISTINCT pr.process_name ORDER BY pr.process_name) FILTER (WHERE pr.process_name IS NOT NULL)
        AS process_names
FROM persons p
JOIN employee_competency_scores ecs ON ecs.person_id = p.person_id
    AND ecs.evaluated_at = (
        SELECT MAX(ecs2.evaluated_at) FROM employee_competency_scores ecs2
        WHERE ecs2.person_id = p.person_id
    )
JOIN process_participations pp ON pp.person_id = p.person_id
JOIN processes pr ON pr.process_id = pp.process_id
LEFT JOIN process_metrics pm ON pm.process_id = pp.process_id
    AND pm.week_start = (
        SELECT MAX(pm2.week_start) FROM process_metrics pm2
        WHERE pm2.process_id = pp.process_id
    )
WHERE ecs.flight_risk_score > 0.5
GROUP BY p.person_id, p.full_name, p.email,
         ecs.flight_risk_score, ecs.overall_score, ecs.evaluated_at
ORDER BY departure_impact_score DESC;


-- V4: Financial waste per process
CREATE OR REPLACE VIEW v_financial_waste AS
SELECT
    p.process_id,
    p.process_name,
    p.department,
    pm.week_start,
    pm.cost_per_unit_pln,
    pm.throughput,
    pm.overdue_rate,
    pm.rework_rate,
    ROUND(
        (pm.cost_per_unit_pln * pm.throughput * (pm.overdue_rate + pm.rework_rate))::numeric, 2
    ) AS estimated_waste_pln_week,
    ar.direction,
    ar.severity,
    ar.attribution_process,
    ar.attribution_people,
    ar.primary_recommendation
FROM process_metrics pm
JOIN processes p ON p.process_id = pm.process_id
LEFT JOIN attribution_results ar ON ar.process_id = pm.process_id
    AND ar.week_start = pm.week_start
WHERE pm.cost_per_unit_pln IS NOT NULL
  AND pm.cost_per_unit_pln > 0
  AND pm.week_start = (
      SELECT MAX(pm2.week_start) FROM process_metrics pm2
      WHERE pm2.process_id = pm.process_id
  )
ORDER BY estimated_waste_pln_week DESC NULLS LAST;

COMMIT;
