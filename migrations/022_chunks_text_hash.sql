-- Add text_hash column to chunks for content-based deduplication (lesson #6)
-- Allows ON CONFLICT DO NOTHING when the same chunk text appears in multiple PST files.

BEGIN;

ALTER TABLE chunks ADD COLUMN IF NOT EXISTS text_hash VARCHAR(32);

-- Backfill existing rows
UPDATE chunks SET text_hash = md5(text) WHERE text_hash IS NULL;

-- Enforce uniqueness per document
CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_document_text_hash
    ON chunks(document_id, text_hash);

COMMIT;
