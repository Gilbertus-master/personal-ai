BEGIN;

CREATE TABLE IF NOT EXISTS guardian_alerts (
    id BIGSERIAL PRIMARY KEY,
    tier INT NOT NULL CHECK (tier IN (1, 2, 3)),
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    fix_command TEXT,
    auto_fix_attempted BOOLEAN DEFAULT FALSE,
    auto_fix_result TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by TEXT,
    repeat_count INT DEFAULT 0,
    last_sent_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guardian_alerts_tier ON guardian_alerts(tier);
CREATE INDEX IF NOT EXISTS idx_guardian_alerts_category ON guardian_alerts(category);
CREATE INDEX IF NOT EXISTS idx_guardian_alerts_ack ON guardian_alerts(acknowledged);
CREATE INDEX IF NOT EXISTS idx_guardian_alerts_created ON guardian_alerts(created_at);
-- Dedup index: find recent alerts by category+title quickly
CREATE INDEX IF NOT EXISTS idx_guardian_alerts_dedup ON guardian_alerts(category, title, created_at);

COMMIT;
