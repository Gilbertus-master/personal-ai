-- Strategic Radar snapshots
-- Stores cross-domain strategic intelligence aggregation results

CREATE TABLE IF NOT EXISTS strategic_radar_snapshots (
    id BIGSERIAL PRIMARY KEY,
    radar_data JSONB NOT NULL DEFAULT '{}',
    patterns JSONB NOT NULL DEFAULT '[]',
    recommendations JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_radar_snapshots_created
    ON strategic_radar_snapshots(created_at DESC);

-- Action Confidence Log
-- Tracks confidence scoring and feedback for auto-action decisions

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

-- Extend action_items with confidence fields
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
        ALTER TABLE action_items ADD COLUMN authority_level INTEGER DEFAULT 2;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'action_items' AND column_name = 'auto_execute_at'
    ) THEN
        ALTER TABLE action_items ADD COLUMN auto_execute_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'action_items' AND column_name = 'signal_type'
    ) THEN
        ALTER TABLE action_items ADD COLUMN signal_type TEXT;
    END IF;
END $$;
