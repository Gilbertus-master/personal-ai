-- Plugin review and proposal tracking tables

CREATE TABLE IF NOT EXISTS omnius_plugin_reviews (
    id BIGSERIAL PRIMARY KEY,
    plugin_version_id BIGINT REFERENCES omnius_plugin_versions(id),
    review_type TEXT NOT NULL CHECK (review_type IN ('automated', 'llm', 'human')),
    reviewer TEXT NOT NULL,
    passed BOOLEAN,
    findings JSONB,
    security_score NUMERIC(3,2),
    quality_score NUMERIC(3,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS omnius_plugin_proposals (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    expected_value TEXT,
    proposed_by BIGINT REFERENCES omnius_users(id),
    governance_result JSONB,
    value_score NUMERIC(3,2),
    duplicate_check JSONB,
    cost_estimate JSONB,
    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending', 'approved', 'rejected', 'developing', 'reviewing', 'deployed'
    )),
    rejection_reason TEXT,
    sandbox_session_id TEXT,
    plugin_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_plugin_reviews_version ON omnius_plugin_reviews(plugin_version_id);
CREATE INDEX idx_proposals_status ON omnius_plugin_proposals(status);
CREATE INDEX idx_proposals_proposed_by ON omnius_plugin_proposals(proposed_by);
