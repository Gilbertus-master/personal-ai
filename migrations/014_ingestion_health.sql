-- Migration 014: Ingestion Health table with UNIQUE constraint + trend
-- 2026-03-29

-- Create table if not exists (Data Guardian already writes to it)
CREATE TABLE IF NOT EXISTS ingestion_health (
    id              SERIAL PRIMARY KEY,
    check_date      DATE NOT NULL,
    source_type     TEXT NOT NULL,
    docs_24h        INTEGER DEFAULT 0,
    docs_7d_avg     NUMERIC(10,1) DEFAULT 0.0,
    status          TEXT DEFAULT 'ok',  -- ok, warning, critical, dead
    trend           TEXT DEFAULT 'stable',  -- growing, stable, declining
    note            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Add UNIQUE constraint (safe if already exists via ON CONFLICT usage)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_ih_date_source'
    ) THEN
        ALTER TABLE ingestion_health
            ADD CONSTRAINT uq_ih_date_source UNIQUE (check_date, source_type);
    END IF;
END$$;

-- Add trend column if missing (table may already exist without it)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ingestion_health' AND column_name = 'trend'
    ) THEN
        ALTER TABLE ingestion_health ADD COLUMN trend TEXT DEFAULT 'stable';
    END IF;
END$$;

-- Index for dashboard queries
CREATE INDEX IF NOT EXISTS idx_ih_date ON ingestion_health (check_date DESC);
CREATE INDEX IF NOT EXISTS idx_ih_source ON ingestion_health (source_type);
