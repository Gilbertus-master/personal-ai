-- Fix roi_activities deduplication: replace plain index with UNIQUE index
-- Removes any pre-existing duplicates (keep lowest id), then enforces uniqueness at DB level.

BEGIN;

-- Remove duplicates: keep the earliest record for each (source_table, source_id) pair
DELETE FROM roi_activities
WHERE id NOT IN (
    SELECT MIN(id)
    FROM roi_activities
    WHERE source_table IS NOT NULL AND source_id IS NOT NULL
    GROUP BY source_table, source_id
);

-- Drop old plain index if it exists
DROP INDEX IF EXISTS idx_roi_activities_source;

-- Create UNIQUE index to atomically prevent concurrent duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_roi_activities_source_unique
    ON roi_activities(source_table, source_id);

COMMIT;
