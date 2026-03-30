-- Migration: Document content-level deduplication
-- Created: 2026-03-30
-- Description: Add content_hash column to documents for cross-path duplicate detection

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'documents' AND column_name = 'content_hash'
    ) THEN
        ALTER TABLE documents ADD COLUMN content_hash TEXT;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_content_hash
    ON documents(content_hash) WHERE content_hash IS NOT NULL;
