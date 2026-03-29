-- Migration 019: Create extraction_coverage_snapshots table
-- Date: 2026-03-29

CREATE TABLE IF NOT EXISTS extraction_coverage_snapshots (
    id BIGSERIAL PRIMARY KEY,
    total_chunks INTEGER NOT NULL,
    covered_chunks INTEGER NOT NULL,
    uncovered_chunks INTEGER NOT NULL,
    coverage_pct NUMERIC(5,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ecs_created ON extraction_coverage_snapshots(created_at DESC);
