-- 012: Sliding Window Conversation Memory
-- Przechowuje ostatnie N wiadomości per kanał/sesja dla multi-turn conversations.

CREATE TABLE IF NOT EXISTS conversation_windows (
    id              BIGSERIAL PRIMARY KEY,
    channel_key     TEXT NOT NULL UNIQUE,   -- "whatsapp:+48505441635", "voice:uuid", "teams:conv_id"
    messages        JSONB NOT NULL DEFAULT '[]',
    message_count   INTEGER NOT NULL DEFAULT 0,
    total_chars     INTEGER NOT NULL DEFAULT 0,
    last_active     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conv_windows_channel ON conversation_windows (channel_key);
CREATE INDEX IF NOT EXISTS idx_conv_windows_active  ON conversation_windows (last_active DESC);
