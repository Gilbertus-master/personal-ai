-- Migration: Action Confidence Scoring
-- Created: 2026-03-29
-- Description: Add confidence scoring columns to action_items, create confidence log table

-- Add confidence columns to action_items (safe: uses IF NOT EXISTS pattern via DO block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'action_items' AND column_name = 'confidence_score'
    ) THEN
        ALTER TABLE action_items ADD COLUMN confidence_score NUMERIC(4,3);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'action_items' AND column_name = 'authority_level'
    ) THEN
        ALTER TABLE action_items ADD COLUMN authority_level INTEGER;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'action_items' AND column_name = 'auto_execute_at'
    ) THEN
        ALTER TABLE action_items ADD COLUMN auto_execute_at TIMESTAMPTZ;
    END IF;
END $$;

-- Action confidence log table
CREATE TABLE IF NOT EXISTS action_confidence_log (
    id BIGSERIAL PRIMARY KEY,
    action_id BIGINT,
    signal_type TEXT,
    confidence NUMERIC(4,3) NOT NULL,
    authority_level INTEGER NOT NULL DEFAULT 2,
    reasoning TEXT,
    approved BOOLEAN,
    executed BOOLEAN,
    outcome TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_confidence_log_action
    ON action_confidence_log(action_id);
CREATE INDEX IF NOT EXISTS idx_confidence_log_signal
    ON action_confidence_log(signal_type);
CREATE INDEX IF NOT EXISTS idx_action_items_auto_execute
    ON action_items(auto_execute_at) WHERE status = 'pending' AND auto_execute_at IS NOT NULL;
