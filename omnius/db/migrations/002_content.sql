-- Omnius content tables: documents, chunks, config

CREATE TABLE IF NOT EXISTS omnius_documents (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT,
    title TEXT,
    content TEXT,
    metadata JSONB,
    department TEXT,
    classification TEXT DEFAULT 'internal'
        CHECK (classification IN ('public', 'internal', 'confidential', 'ceo_only')),
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS omnius_chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES omnius_documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding_id TEXT,
    classification TEXT DEFAULT 'internal'
        CHECK (classification IN ('public', 'internal', 'confidential', 'ceo_only')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_source_id ON omnius_documents(source_id)
    WHERE source_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chunks_classification ON omnius_chunks(classification);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON omnius_chunks(document_id);

-- Full-text search (MVP — no Qdrant)
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON omnius_chunks
    USING gin(to_tsvector('simple', content));

CREATE TABLE IF NOT EXISTS omnius_config (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value JSONB NOT NULL,
    pushed_by TEXT DEFAULT 'gilbertus',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
