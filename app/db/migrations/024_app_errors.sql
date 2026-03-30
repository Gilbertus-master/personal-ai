-- Multi-user error reporting table
CREATE TABLE IF NOT EXISTS app_errors (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT DEFAULT 'unknown',
    route TEXT,
    error_type TEXT NOT NULL,       -- 'runtime', 'network', 'render', 'api'
    error_message TEXT NOT NULL,
    error_stack TEXT,
    component TEXT,                 -- np. 'OrgHealthBanner'
    module TEXT,                    -- np. 'intelligence', 'compliance'
    browser TEXT,
    user_agent TEXT,
    app_version TEXT DEFAULT '0.1',
    resolved BOOLEAN DEFAULT FALSE,
    fix_commit TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_app_errors_unresolved ON app_errors(resolved, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_app_errors_route ON app_errors(route, resolved);
