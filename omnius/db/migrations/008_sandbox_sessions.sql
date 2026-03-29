-- Sandbox session tracking for plugin development containers
CREATE TABLE IF NOT EXISTS omnius_sandbox_sessions (
    id TEXT PRIMARY KEY,
    plugin_name TEXT,
    proposal_id BIGINT,
    container_id TEXT,
    status TEXT DEFAULT 'creating' CHECK (status IN ('creating', 'running', 'completed', 'timeout', 'error', 'destroyed')),
    started_by BIGINT REFERENCES omnius_users(id),
    api_calls_count INTEGER DEFAULT 0,
    api_cost_usd NUMERIC(10,4) DEFAULT 0,
    output_path TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    timeout_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 minutes'
);

CREATE INDEX IF NOT EXISTS idx_sandbox_status ON omnius_sandbox_sessions(status);
CREATE INDEX IF NOT EXISTS idx_sandbox_started_by ON omnius_sandbox_sessions(started_by);
