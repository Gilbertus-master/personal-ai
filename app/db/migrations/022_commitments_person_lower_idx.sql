-- Migration: Add functional index on LOWER(person_name) for commitments
-- Created: 2026-03-30
-- Description: Allows PostgreSQL to use an index for LOWER(person_name) = LOWER(%s) filters
--              used in delegation_tracker.py (lines 44, 71, 84, 115).

CREATE INDEX IF NOT EXISTS idx_commitments_person_lower ON commitments (LOWER(person_name));
