-- 009_cost_budgets.sql — API cost budgets & circuit breaker
-- 2026-03-28

CREATE TABLE IF NOT EXISTS cost_budgets (
    id SERIAL PRIMARY KEY,
    scope TEXT NOT NULL UNIQUE,          -- 'daily_total', 'module:retrieval.answering', etc.
    limit_usd NUMERIC(10,4) NOT NULL,
    alert_threshold_pct INT NOT NULL DEFAULT 80,  -- warn at 80%
    hard_limit BOOLEAN NOT NULL DEFAULT FALSE,    -- if TRUE, block calls when exceeded
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default budgets
INSERT INTO cost_budgets (scope, limit_usd, alert_threshold_pct, hard_limit) VALUES
    ('daily_total',                5.0000,  80, TRUE),
    ('module:retrieval.answering', 2.0000,  80, FALSE),
    ('module:extraction',         2.0000,  80, FALSE),
    ('module:analysis',           1.0000,  80, FALSE)
ON CONFLICT (scope) DO NOTHING;

-- Track when alerts were last sent to avoid spam
CREATE TABLE IF NOT EXISTS cost_alert_log (
    id SERIAL PRIMARY KEY,
    scope TEXT NOT NULL,
    alert_type TEXT NOT NULL,        -- 'warning', 'hard_limit', 'info'
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cost_alert_log_scope_date
    ON cost_alert_log (scope, created_at DESC);
