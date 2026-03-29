-- Extend omnius_plugin_proposals with email tracking and review result storage

ALTER TABLE omnius_plugin_proposals
    ADD COLUMN IF NOT EXISTS proposed_by_email TEXT,
    ADD COLUMN IF NOT EXISTS review_result JSONB;

CREATE INDEX IF NOT EXISTS idx_proposals_email ON omnius_plugin_proposals(proposed_by_email);
