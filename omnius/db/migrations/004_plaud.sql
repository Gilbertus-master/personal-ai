-- Per-user Plaud configuration and audio transcription support

-- Plaud credentials per user
CREATE TABLE IF NOT EXISTS omnius_plaud_config (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES omnius_users(id),
    plaud_auth_token TEXT,              -- Plaud API JWT (encrypted at rest)
    webhook_secret TEXT,                -- HMAC secret for webhook verification
    device_name TEXT DEFAULT 'Plaud Pin S',
    auto_sync BOOLEAN NOT NULL DEFAULT TRUE,
    sync_interval_minutes INTEGER DEFAULT 15,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Classification rules for audio: which recordings are personal vs corporate
CREATE TABLE IF NOT EXISTS omnius_audio_rules (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES omnius_users(id),
    rule_type TEXT NOT NULL CHECK (rule_type IN ('keyword', 'participant', 'time_range', 'default')),
    pattern TEXT NOT NULL,               -- keyword, participant name, or time range (HH:MM-HH:MM)
    classification TEXT NOT NULL DEFAULT 'corporate'
        CHECK (classification IN ('personal', 'corporate', 'confidential', 'ceo_only')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default rule: all recordings are corporate unless matched by personal rule
INSERT INTO omnius_audio_rules (user_id, rule_type, pattern, classification)
SELECT u.id, 'default', '*', 'corporate'
FROM omnius_users u
WHERE u.role_id IN (SELECT id FROM omnius_roles WHERE name IN ('ceo', 'board'))
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_plaud_config_user ON omnius_plaud_config(user_id);
CREATE INDEX IF NOT EXISTS idx_audio_rules_user ON omnius_audio_rules(user_id);

-- Add owner_user_id to documents for per-user audio ownership
ALTER TABLE omnius_documents ADD COLUMN IF NOT EXISTS owner_user_id BIGINT REFERENCES omnius_users(id);
CREATE INDEX IF NOT EXISTS idx_documents_owner ON omnius_documents(owner_user_id);
