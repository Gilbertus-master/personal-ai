-- Add composite partial index on rel_patterns(partner_id, active)
-- Speeds up get_active_patterns() and get_alerts() queries
-- CONCURRENTLY cannot run inside a transaction block
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rel_patterns_partner_active
    ON rel_patterns (partner_id, active)
    WHERE active = TRUE;
