CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMPTZ,
    author TEXT,
    participants JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_path TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    timestamp_start TIMESTAMPTZ,
    timestamp_end TIMESTAMPTZ,
    embedding_id TEXT,
    CONSTRAINT chunks_document_chunk_index_unique UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS entities (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    CONSTRAINT entities_name_type_unique UNIQUE (name, entity_type)
);

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_time TIMESTAMPTZ,
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    id BIGSERIAL PRIMARY KEY,
    summary_type TEXT NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    text TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_source_type
    ON sources(source_type);

CREATE INDEX IF NOT EXISTS idx_documents_source_id
    ON documents(source_id);

CREATE INDEX IF NOT EXISTS idx_documents_created_at
    ON documents(created_at);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id
    ON chunks(document_id);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_id
    ON chunks(embedding_id);

CREATE INDEX IF NOT EXISTS idx_entities_entity_type
    ON entities(entity_type);

CREATE INDEX IF NOT EXISTS idx_events_document_id
    ON events(document_id);

CREATE INDEX IF NOT EXISTS idx_events_event_time
    ON events(event_time);

CREATE INDEX IF NOT EXISTS idx_summaries_summary_type
    ON summaries(summary_type);

CREATE INDEX IF NOT EXISTS idx_summaries_period_start
    ON summaries(period_start);

CREATE INDEX IF NOT EXISTS idx_summaries_period_end
    ON summaries(period_end);