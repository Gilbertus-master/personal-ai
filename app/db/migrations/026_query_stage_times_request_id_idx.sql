-- Migration 026: Add index on request_id for query_stage_times table
-- Description: The request_id column is the natural lookup key for debugging individual
--              requests. Without an index, queries looking up timing data for a specific
--              request will do a full sequential scan on what can become a large table.
-- Created: 2026-03-31

CREATE INDEX IF NOT EXISTS idx_qst_request_id ON query_stage_times (request_id) WHERE request_id IS NOT NULL;
