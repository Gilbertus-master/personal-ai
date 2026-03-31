-- Attribution Engine tables
-- Run: psql -U gilbertus -d gilbertus -f 001_attribution_tables.sql

BEGIN;

CREATE TABLE IF NOT EXISTS attribution_results (
    attribution_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id       UUID NOT NULL REFERENCES processes(process_id),
    week_start       DATE NOT NULL,

    direction        TEXT NOT NULL CHECK (direction IN ('problem', 'success', 'neutral')),
    severity         TEXT CHECK (severity IN ('critical', 'high', 'medium', 'low')),

    attribution_process     FLOAT NOT NULL DEFAULT 0.0,
    attribution_people      FLOAT NOT NULL DEFAULT 0.0,
    attribution_interaction FLOAT NOT NULL DEFAULT 0.0,
    attribution_external    FLOAT NOT NULL DEFAULT 0.0,
    attribution_unknown     FLOAT NOT NULL DEFAULT 0.0,

    confidence              FLOAT NOT NULL DEFAULT 0.0,
    data_points_count       INT NOT NULL DEFAULT 0,
    min_weeks_data          INT NOT NULL DEFAULT 0,

    process_signals         JSONB DEFAULT '{}',
    people_signals          JSONB DEFAULT '{}',
    interaction_signals     JSONB DEFAULT '{}',

    team_id                 TEXT,
    team_health_contribution FLOAT,

    top_people_positive     JSONB DEFAULT '[]',
    top_people_negative     JSONB DEFAULT '[]',

    primary_recommendation  TEXT,
    recommendation_type     TEXT,
    narrative               TEXT,
    ai_confidence           FLOAT,

    computed_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (process_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_attribution_results_week ON attribution_results(week_start);
CREATE INDEX IF NOT EXISTS idx_attribution_results_direction ON attribution_results(direction);
CREATE INDEX IF NOT EXISTS idx_attribution_results_severity ON attribution_results(severity);
CREATE INDEX IF NOT EXISTS idx_attribution_results_team ON attribution_results(team_id);
CREATE INDEX IF NOT EXISTS idx_attribution_results_process ON attribution_results(process_id);


CREATE TABLE IF NOT EXISTS org_health_snapshots (
    snapshot_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    week_start          DATE NOT NULL UNIQUE,

    org_health_score    SMALLINT NOT NULL,
    org_health_label    TEXT NOT NULL,
    score_delta_1w      FLOAT,
    score_delta_4w      FLOAT,

    -- Q1: Money
    financial_waste_pln NUMERIC(12, 2),
    top_cost_processes  JSONB DEFAULT '[]',
    budget_overruns_count INT DEFAULT 0,

    -- Q2: People
    critical_people_at_risk INT DEFAULT 0,
    high_impact_departures  JSONB DEFAULT '[]',
    team_instability_score  FLOAT DEFAULT 0.0,

    -- Q3: Process
    process_health_avg    FLOAT DEFAULT 0.0,
    critical_processes    INT DEFAULT 0,
    processes_improving   INT DEFAULT 0,
    processes_declining   INT DEFAULT 0,

    -- Q4: Investment
    top_investment_opps   JSONB DEFAULT '[]',

    dept_health_breakdown JSONB DEFAULT '{}',
    critical_alerts       JSONB DEFAULT '[]',
    warning_alerts        JSONB DEFAULT '[]',

    computed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_org_health_week ON org_health_snapshots(week_start);
CREATE INDEX IF NOT EXISTS idx_org_health_score ON org_health_snapshots(org_health_score);

COMMIT;
