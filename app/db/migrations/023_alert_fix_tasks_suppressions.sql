-- Alert resolution workflow: fix tasks + suppression rules
-- 2026-03-31

CREATE TABLE IF NOT EXISTS alert_fix_tasks (
    id SERIAL PRIMARY KEY,
    alert_id BIGINT REFERENCES alerts(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    instruction TEXT NOT NULL,
    comment TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'done', 'failed')),
    result TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_fix_tasks_status ON alert_fix_tasks(status);
CREATE INDEX IF NOT EXISTS idx_alert_fix_tasks_alert_id ON alert_fix_tasks(alert_id);

CREATE TABLE IF NOT EXISTS alert_suppressions (
    id SERIAL PRIMARY KEY,
    alert_type TEXT NOT NULL,
    source_type TEXT,
    reason TEXT,
    created_by TEXT DEFAULT 'sebastian',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_suppressions_unique
    ON alert_suppressions(alert_type, COALESCE(source_type, '__null__'));
CREATE INDEX IF NOT EXISTS idx_alert_suppressions_type ON alert_suppressions(alert_type);
