BEGIN;

-- ============================================================
-- 1. processes — process definitions
-- ============================================================
CREATE TABLE IF NOT EXISTS processes (
    process_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_name        TEXT NOT NULL,
    process_type        TEXT NOT NULL CHECK (process_type IN (
                            'engineering', 'sales', 'customer_service', 'finance', 'operations'
                        )),
    process_category    TEXT,
    parent_process_id   UUID REFERENCES processes(process_id),
    team_id             TEXT,
    sla_target_hours    FLOAT,
    cost_per_unit_pln   FLOAT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 2. process_metrics — weekly aggregates per process
-- ============================================================
CREATE TABLE IF NOT EXISTS process_metrics (
    metric_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id              UUID NOT NULL REFERENCES processes(process_id),
    week_start              DATE NOT NULL,

    -- Flow metrics
    throughput              INT,
    avg_cycle_time_h        FLOAT,
    p90_cycle_time_h        FLOAT,
    overdue_count           INT,
    overdue_rate            FLOAT,
    error_rate              FLOAT,
    rework_rate             FLOAT,

    -- Jira / engineering planning
    velocity_points         INT,
    velocity_vs_plan        FLOAT,
    bugs_introduced         INT,
    blockers_count          INT,
    wip_count               INT,
    lead_time_days          FLOAT,
    flow_efficiency         FLOAT,

    -- Sales
    revenue_pln             NUMERIC(12,2),
    deals_closed            INT,
    deals_lost              INT,
    conversion_rate         FLOAT,
    avg_deal_size_pln       NUMERIC(12,2),
    avg_sales_cycle_days    FLOAT,
    pipeline_value_pln      NUMERIC(12,2),
    quota_attainment        FLOAT,

    -- Customer service
    tickets_resolved        INT,
    avg_first_response_h    FLOAT,
    avg_resolution_h        FLOAT,
    escalation_rate         FLOAT,
    csat_score              FLOAT,
    nps_score               FLOAT,
    first_contact_resolution_rate FLOAT,

    -- Engineering / CI-CD
    deployments_count       INT,
    deployment_failures     INT,
    change_failure_rate     FLOAT,
    mttr_hours              FLOAT,
    code_coverage_pct       FLOAT,
    critical_bugs_open      INT,
    tech_debt_hours         INT,

    -- Finance
    cost_actual_pln         NUMERIC(12,2),
    cost_budget_pln         NUMERIC(12,2),
    budget_variance_pct     FLOAT,
    margin_pct              FLOAT,
    cost_per_unit           FLOAT,

    -- Health
    process_health_score    FLOAT,
    health_trend            FLOAT,
    anomaly_flags           TEXT[],

    -- Meta
    sources_collected       TEXT[],
    collection_errors       JSONB,
    collected_at            TIMESTAMPTZ DEFAULT now(),

    UNIQUE (process_id, week_start)
);

-- ============================================================
-- 3. process_participations — who participated in which process
-- ============================================================
CREATE TABLE IF NOT EXISTS process_participations (
    participation_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id              UUID NOT NULL REFERENCES processes(process_id),
    person_id               UUID NOT NULL REFERENCES persons(person_id),
    week_start              DATE NOT NULL,

    role_in_process         TEXT NOT NULL CHECK (role_in_process IN (
                                'owner', 'contributor', 'reviewer', 'blocked_by',
                                'blocking', 'escalated_to', 'approver', 'executor'
                            )),

    tasks_owned             INT DEFAULT 0,
    tasks_contributed       INT DEFAULT 0,
    reviews_done            INT DEFAULT 0,
    escalations_caused      INT DEFAULT 0,
    blockers_caused         INT DEFAULT 0,
    avg_response_time_h     FLOAT,
    tasks_overdue_owned     INT DEFAULT 0,
    ownership_pct           FLOAT,

    UNIQUE (process_id, person_id, week_start)
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_pm_process_week ON process_metrics (process_id, week_start);
CREATE INDEX IF NOT EXISTS idx_pm_health       ON process_metrics (process_health_score);
CREATE INDEX IF NOT EXISTS idx_pp_person       ON process_participations (person_id);
CREATE INDEX IF NOT EXISTS idx_pp_process      ON process_participations (process_id, week_start);

COMMIT;
