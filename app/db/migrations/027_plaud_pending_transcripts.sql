CREATE TABLE IF NOT EXISTS plaud_pending_transcripts (
    file_id TEXT PRIMARY KEY,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plaud_pending_last_checked
    ON plaud_pending_transcripts(last_checked_at);
