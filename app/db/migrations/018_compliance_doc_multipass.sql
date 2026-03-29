-- Migration 018: Add multipass generation columns to compliance_documents
-- Date: 2026-03-29

ALTER TABLE compliance_documents ADD COLUMN IF NOT EXISTS is_complete BOOLEAN DEFAULT FALSE;
ALTER TABLE compliance_documents ADD COLUMN IF NOT EXISTS word_count INTEGER;
ALTER TABLE compliance_documents ADD COLUMN IF NOT EXISTS section_count INTEGER;
ALTER TABLE compliance_documents ADD COLUMN IF NOT EXISTS quality_score NUMERIC(3,2);
ALTER TABLE compliance_documents ADD COLUMN IF NOT EXISTS generation_method TEXT DEFAULT 'single_shot';
