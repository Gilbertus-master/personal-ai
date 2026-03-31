-- Process Evaluator: competency scores, matrix view, human-risk view
-- Mirrors employee_competency_scores pattern for processes

BEGIN;

-- ── Main scores table ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS process_competency_scores (
    score_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id          UUID NOT NULL REFERENCES processes(process_id) ON DELETE CASCADE,
    cycle_id            UUID REFERENCES evaluation_cycles(cycle_id),

    -- D1: Throughput
    score_throughput        FLOAT,
    throughput_evidence     JSONB,
    throughput_confidence   FLOAT,

    -- D2: Quality
    score_quality           FLOAT,
    quality_evidence        JSONB,
    quality_confidence      FLOAT,

    -- D3: Maturity
    score_maturity          FLOAT,
    maturity_evidence       JSONB,
    maturity_confidence     FLOAT,
    process_maturity_level  SMALLINT,
    maturity_survey_date    TIMESTAMPTZ,

    -- D4: Handoff
    score_handoff           FLOAT,
    handoff_evidence        JSONB,
    handoff_confidence      FLOAT,

    -- D5: Cost
    score_cost              FLOAT,
    cost_evidence           JSONB,
    cost_confidence         FLOAT,
    cost_per_unit_pln       FLOAT,
    cost_vs_benchmark       FLOAT,

    -- D6: Improvement
    score_improvement       FLOAT,
    improvement_evidence    JSONB,
    improvement_confidence  FLOAT,

    -- D7: Scalability
    score_scalability       FLOAT,
    scalability_evidence    JSONB,
    scalability_confidence  FLOAT,
    capacity_headroom_pct   FLOAT,
    estimated_breaking_point_x FLOAT,

    -- D8: Dependency
    score_dependency        FLOAT,
    dependency_evidence     JSONB,
    dependency_confidence   FLOAT,
    bus_factor              INT,
    knowledge_concentration FLOAT,
    flight_risk_weighted    FLOAT,
    upstream_risk_score     FLOAT,
    critical_person_ids     UUID[],

    -- Composite scores
    overall_health_score    FLOAT,
    health_label            TEXT,
    failure_risk_score      FLOAT,

    -- Process box (Health x Maturity)
    process_box_health      TEXT,
    process_box_maturity    TEXT,
    process_box_label       TEXT,

    -- Data window
    data_period_start       DATE,
    data_period_end         DATE,
    events_analyzed         INT,
    data_completeness       FLOAT,

    -- Control
    requires_human_review   BOOLEAN DEFAULT TRUE,
    ai_narrative            TEXT,
    ai_key_findings         TEXT[],
    ai_recommendations      TEXT[],
    ai_model_used           TEXT,

    computed_at             TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(process_id, cycle_id)
);

CREATE INDEX IF NOT EXISTS idx_pcs_process ON process_competency_scores(process_id);
CREATE INDEX IF NOT EXISTS idx_pcs_health  ON process_competency_scores(overall_health_score);
CREATE INDEX IF NOT EXISTS idx_pcs_risk    ON process_competency_scores(failure_risk_score DESC);

-- ── View: process matrix ───────────────────────────────────────────
CREATE OR REPLACE VIEW v_process_matrix AS
SELECT
    p.process_id,
    p.process_name,
    p.process_type,
    p.status        AS process_status,
    pcs.overall_health_score,
    pcs.health_label,
    pcs.failure_risk_score,
    pcs.process_box_label,
    pcs.score_throughput,
    pcs.score_quality,
    pcs.score_maturity,
    pcs.score_handoff,
    pcs.score_cost,
    pcs.score_improvement,
    pcs.score_scalability,
    pcs.score_dependency,
    pcs.bus_factor,
    pcs.flight_risk_weighted,
    pcs.process_maturity_level,
    pcs.data_completeness,
    pcs.computed_at
FROM processes p
JOIN LATERAL (
    SELECT *
    FROM process_competency_scores pcs2
    WHERE pcs2.process_id = p.process_id
    ORDER BY pcs2.computed_at DESC
    LIMIT 1
) pcs ON TRUE
ORDER BY pcs.failure_risk_score DESC NULLS LAST;

-- ── View: processes at human risk ──────────────────────────────────
CREATE OR REPLACE VIEW v_processes_at_human_risk AS
SELECT
    p.process_id,
    p.process_name,
    p.process_type,
    pcs.overall_health_score,
    pcs.health_label,
    pcs.failure_risk_score,
    pcs.bus_factor,
    pcs.flight_risk_weighted,
    pcs.knowledge_concentration,
    pcs.critical_person_ids,
    (
        SELECT jsonb_agg(jsonb_build_object(
            'person_id', pp2.person_id,
            'name', per.display_name,
            'flight_risk', ecs.flight_risk_score,
            'ownership_pct', pp2.ownership_pct,
            'job_title', prof.job_title
        ))
        FROM process_participations pp2
        JOIN persons per ON per.person_id = pp2.person_id
        LEFT JOIN employee_competency_scores ecs
            ON ecs.person_id = pp2.person_id
            AND ecs.scored_at = (
                SELECT MAX(scored_at) FROM employee_competency_scores
                WHERE person_id = pp2.person_id
            )
        LEFT JOIN person_professional prof
            ON prof.person_id = pp2.person_id
        WHERE pp2.process_id = p.process_id
          AND pp2.ownership_pct > 0.2
    ) AS critical_persons_detail,
    pcs.computed_at
FROM processes p
JOIN LATERAL (
    SELECT *
    FROM process_competency_scores pcs2
    WHERE pcs2.process_id = p.process_id
    ORDER BY pcs2.computed_at DESC
    LIMIT 1
) pcs ON TRUE
WHERE pcs.flight_risk_weighted > 0.5
   OR pcs.bus_factor = 1
ORDER BY pcs.failure_risk_score DESC NULLS LAST;

COMMIT;
