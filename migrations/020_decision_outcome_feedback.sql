-- Migration 020: Decision Outcome Suggestions + Decision Action Links + Answer Evaluations + Threshold Optimization Log
-- Area D: Decision Outcome Detector
-- Area C: Feedback Persistence

-- Decision outcome suggestions (auto-detected by LLM)
CREATE TABLE IF NOT EXISTS decision_outcome_suggestions (
    id BIGSERIAL PRIMARY KEY,
    decision_id BIGINT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    suggested_outcome TEXT NOT NULL,
    suggested_rating INTEGER CHECK (suggested_rating BETWEEN 1 AND 5),
    evidence_summary TEXT,
    confidence NUMERIC(3,2) DEFAULT 0.5,
    accepted BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(decision_id)
);
CREATE INDEX IF NOT EXISTS idx_decision_outcome_sugg_decision
ON decision_outcome_suggestions(decision_id);

-- Decision-to-action links (keyword matched ±48h)
CREATE TABLE IF NOT EXISTS decision_action_links (
    id BIGSERIAL PRIMARY KEY,
    decision_id BIGINT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    action_item_id BIGINT NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,
    link_type TEXT DEFAULT 'keyword',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(decision_id, action_item_id)
);
CREATE INDEX IF NOT EXISTS idx_decision_action_links_decision
ON decision_action_links(decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_action_links_action
ON decision_action_links(action_item_id);

-- Answer evaluations (from Evaluator-Optimizer pattern)
CREATE TABLE IF NOT EXISTS answer_evaluations (
    id BIGSERIAL PRIMARY KEY,
    ask_run_id BIGINT REFERENCES ask_runs(id) ON DELETE SET NULL,
    relevance NUMERIC(3,2) NOT NULL,
    grounding NUMERIC(3,2) NOT NULL,
    depth NUMERIC(3,2) NOT NULL,
    overall NUMERIC(3,2) NOT NULL,
    feedback TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_answer_evaluations_run
ON answer_evaluations(ask_run_id);
CREATE INDEX IF NOT EXISTS idx_answer_evaluations_created
ON answer_evaluations(created_at);
CREATE INDEX IF NOT EXISTS idx_answer_evaluations_overall
ON answer_evaluations(overall);

-- Threshold optimization log
CREATE TABLE IF NOT EXISTS threshold_optimization_log (
    id BIGSERIAL PRIMARY KEY,
    optimization_type TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    old_value NUMERIC,
    new_value NUMERIC,
    reason TEXT,
    applied BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_threshold_opt_type
ON threshold_optimization_log(optimization_type);
CREATE INDEX IF NOT EXISTS idx_threshold_opt_created
ON threshold_optimization_log(created_at);
