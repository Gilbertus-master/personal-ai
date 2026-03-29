-- Migration: Strategic Radar Snapshots
-- Created: 2026-03-29
-- Description: Table for storing strategic radar snapshots with patterns and recommendations

CREATE TABLE IF NOT EXISTS strategic_radar_snapshots (
    id BIGSERIAL PRIMARY KEY,
    radar_data JSONB NOT NULL,
    patterns JSONB NOT NULL DEFAULT '[]',
    recommendations JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_radar_snapshots_created
    ON strategic_radar_snapshots(created_at DESC);
