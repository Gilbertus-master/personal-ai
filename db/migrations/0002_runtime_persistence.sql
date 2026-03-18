BEGIN;

CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    title TEXT,
    entrypoint TEXT NOT NULL DEFAULT 'api'
);

CREATE TABLE IF NOT EXISTS ask_runs (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT REFERENCES sessions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    query_text TEXT NOT NULL,
    normalized_query TEXT,
    question_type TEXT,
    analysis_depth TEXT,

    top_k INTEGER NOT NULL,
    prefetch_k INTEGER,
    answer_match_limit INTEGER,

    source_types JSONB,
    source_names JSONB,
    date_from DATE,
    date_to DATE,

    used_fallback BOOLEAN NOT NULL DEFAULT FALSE,
    match_count INTEGER NOT NULL DEFAULT 0,

    answer_text TEXT NOT NULL,
    answer_length TEXT,
    allow_quotes BOOLEAN NOT NULL DEFAULT FALSE,
    debug BOOLEAN NOT NULL DEFAULT FALSE,
    latency_ms INTEGER,

    raw_request_json JSONB NOT NULL,
    raw_response_json JSONB
);

CREATE TABLE IF NOT EXISTS ask_run_matches (
    id BIGSERIAL PRIMARY KEY,
    ask_run_id BIGINT NOT NULL REFERENCES ask_runs(id) ON DELETE CASCADE,
    chunk_id BIGINT,
    document_id BIGINT,
    rank_index INTEGER NOT NULL,
    score DOUBLE PRECISION,
    source_type TEXT,
    source_name TEXT,
    title TEXT,
    created_at TIMESTAMPTZ,
    excerpt TEXT
);

CREATE INDEX IF NOT EXISTS idx_ask_runs_created_at
    ON ask_runs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ask_runs_session_id
    ON ask_runs(session_id);

CREATE INDEX IF NOT EXISTS idx_ask_run_matches_ask_run_id
    ON ask_run_matches(ask_run_id);

COMMIT;
