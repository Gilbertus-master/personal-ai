-- employee_evaluator: multi-dimensional employee evaluation with GDPR compliance
-- Created: 2026-03-31

BEGIN;

-- ── 1. Organization configs ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS org_configs (
    id              SERIAL PRIMARY KEY,
    org_key         TEXT NOT NULL UNIQUE DEFAULT 'default',
    evaluation_mode TEXT NOT NULL DEFAULT 'development'
        CHECK (evaluation_mode IN ('development', 'performance')),
    content_analysis_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    legal_basis     TEXT NOT NULL DEFAULT 'legitimate_interest',
    employees_notified_at TIMESTAMPTZ,
    default_retention_days INT NOT NULL DEFAULT 730,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO org_configs (org_key) VALUES ('default') ON CONFLICT DO NOTHING;

-- ── 2. Role configs ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS role_configs (
    id              SERIAL PRIMARY KEY,
    role_name       TEXT NOT NULL UNIQUE,
    seniority_level TEXT NOT NULL DEFAULT 'mid'
        CHECK (seniority_level IN ('junior', 'mid', 'senior', 'lead', 'director', 'executive')),
    w_delivery      FLOAT NOT NULL DEFAULT 0.20,
    w_collaboration FLOAT NOT NULL DEFAULT 0.15,
    w_communication FLOAT NOT NULL DEFAULT 0.10,
    w_initiative    FLOAT NOT NULL DEFAULT 0.10,
    w_knowledge     FLOAT NOT NULL DEFAULT 0.10,
    w_leadership    FLOAT NOT NULL DEFAULT 0.10,
    w_growth        FLOAT NOT NULL DEFAULT 0.10,
    w_relationships FLOAT NOT NULL DEFAULT 0.15,
    -- Expected benchmarks (score=3.0 target values)
    bench_tasks_completed_ratio   FLOAT DEFAULT 0.75,
    bench_response_time_hours     FLOAT DEFAULT 4.0,
    bench_pr_review_ratio         FLOAT DEFAULT 0.5,
    bench_meeting_participation   FLOAT DEFAULT 0.70,
    bench_docs_per_month          FLOAT DEFAULT 2.0,
    bench_initiative_ratio        FLOAT DEFAULT 0.20,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 3. Evaluation cycles ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS evaluation_cycles (
    cycle_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_name      TEXT NOT NULL,
    cycle_type      TEXT NOT NULL DEFAULT 'quarterly'
        CHECK (cycle_type IN ('monthly', 'quarterly', 'semi_annual', 'annual', 'ad_hoc')),
    evaluation_mode TEXT NOT NULL DEFAULT 'development'
        CHECK (evaluation_mode IN ('development', 'performance')),
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'in_progress', 'review', 'completed', 'archived')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evaluation_cycles_status ON evaluation_cycles(status);

-- ── 4. Employee signals ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS employee_signals (
    id              BIGSERIAL PRIMARY KEY,
    person_id       UUID NOT NULL,
    week_start      DATE NOT NULL,

    -- Teams / messaging
    teams_messages_sent     INT DEFAULT 0,
    teams_messages_received INT DEFAULT 0,
    teams_reactions_given   INT DEFAULT 0,
    teams_meetings_attended INT DEFAULT 0,
    teams_meetings_organized INT DEFAULT 0,

    -- Email
    emails_sent             INT DEFAULT 0,
    emails_received         INT DEFAULT 0,
    emails_avg_response_hours FLOAT,

    -- Code / commits
    commits_count           INT DEFAULT 0,
    commits_lines_added     INT DEFAULT 0,
    commits_lines_removed   INT DEFAULT 0,
    commits_pr_reviews      INT DEFAULT 0,

    -- Tasks / projects
    tasks_created           INT DEFAULT 0,
    tasks_completed         INT DEFAULT 0,
    tasks_assigned          INT DEFAULT 0,
    tasks_overdue           INT DEFAULT 0,
    tasks_blockers_resolved INT DEFAULT 0,

    -- Documents
    docs_created            INT DEFAULT 0,
    docs_edited             INT DEFAULT 0,

    -- HR
    hr_absences_days        FLOAT DEFAULT 0,
    hr_training_hours       FLOAT DEFAULT 0,
    hr_feedback_given       INT DEFAULT 0,
    hr_feedback_received    INT DEFAULT 0,

    collected_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(person_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_employee_signals_person ON employee_signals(person_id);
CREATE INDEX IF NOT EXISTS idx_employee_signals_week ON employee_signals(week_start);

-- ── 5. Competency scores ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS employee_competency_scores (
    id                  BIGSERIAL PRIMARY KEY,
    person_id           UUID NOT NULL,
    cycle_id            UUID NOT NULL REFERENCES evaluation_cycles(cycle_id),

    -- 8 competencies
    delivery_score      FLOAT,
    delivery_evidence   JSONB,
    delivery_confidence FLOAT DEFAULT 0,

    collaboration_score      FLOAT,
    collaboration_evidence   JSONB,
    collaboration_confidence FLOAT DEFAULT 0,

    communication_score      FLOAT,
    communication_evidence   JSONB,
    communication_confidence FLOAT DEFAULT 0,

    initiative_score      FLOAT,
    initiative_evidence   JSONB,
    initiative_confidence FLOAT DEFAULT 0,

    knowledge_score      FLOAT,
    knowledge_evidence   JSONB,
    knowledge_confidence FLOAT DEFAULT 0,

    leadership_score      FLOAT,
    leadership_evidence   JSONB,
    leadership_confidence FLOAT DEFAULT 0,

    growth_score      FLOAT,
    growth_evidence   JSONB,
    growth_confidence FLOAT DEFAULT 0,

    relationships_score      FLOAT,
    relationships_evidence   JSONB,
    relationships_confidence FLOAT DEFAULT 0,

    -- Aggregates
    overall_score       FLOAT,
    overall_label       TEXT,
    potential_score     FLOAT,
    flight_risk_score   FLOAT,
    data_completeness   FLOAT DEFAULT 0,

    requires_human_review BOOLEAN NOT NULL DEFAULT TRUE,

    scored_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(person_id, cycle_id)
);

CREATE INDEX IF NOT EXISTS idx_competency_scores_person ON employee_competency_scores(person_id);
CREATE INDEX IF NOT EXISTS idx_competency_scores_cycle ON employee_competency_scores(cycle_id);

-- ── 6. Employee reports ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS employee_reports (
    id                  BIGSERIAL PRIMARY KEY,
    person_id           UUID NOT NULL,
    cycle_id            UUID NOT NULL REFERENCES evaluation_cycles(cycle_id),

    report_type         TEXT NOT NULL DEFAULT 'manager_only'
        CHECK (report_type IN ('manager_only', 'self_review', 'peer_feedback', 'full_360')),

    executive_summary   TEXT,
    narrative_strengths TEXT,
    narrative_development TEXT,
    key_strengths       JSONB,         -- TEXT[]
    development_areas   JSONB,         -- TEXT[]
    suggested_actions   JSONB,         -- TEXT[]

    nine_box_performance TEXT,
    nine_box_potential   TEXT,
    nine_box_label       TEXT,

    gdpr_basis          TEXT NOT NULL DEFAULT 'legitimate_interest',
    retention_until     DATE NOT NULL DEFAULT (CURRENT_DATE + INTERVAL '2 years'),

    requires_human_review BOOLEAN NOT NULL DEFAULT TRUE,

    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(person_id, cycle_id, report_type)
);

CREATE INDEX IF NOT EXISTS idx_employee_reports_person ON employee_reports(person_id);
CREATE INDEX IF NOT EXISTS idx_employee_reports_cycle ON employee_reports(cycle_id);
CREATE INDEX IF NOT EXISTS idx_employee_reports_retention ON employee_reports(retention_until);

-- ── 7. Audit log ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS evaluation_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    person_id       UUID,
    action          TEXT NOT NULL,
    performed_by    TEXT NOT NULL DEFAULT 'system',
    details         JSONB,
    logged_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_audit_person ON evaluation_audit_log(person_id);
CREATE INDEX IF NOT EXISTS idx_eval_audit_action ON evaluation_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_eval_audit_logged ON evaluation_audit_log(logged_at);

COMMIT;
