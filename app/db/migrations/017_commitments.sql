-- Commitment Tracker
CREATE TABLE IF NOT EXISTS commitments (
    id BIGSERIAL PRIMARY KEY,
    person_name TEXT NOT NULL,
    person_id BIGINT REFERENCES people(id),
    commitment_text TEXT NOT NULL,
    context TEXT,
    deadline TIMESTAMPTZ,
    source_chunk_id BIGINT REFERENCES chunks(id),
    source_event_id BIGINT REFERENCES events(id),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'fulfilled', 'broken', 'overdue', 'cancelled')),
    fulfilled_evidence TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(status);
CREATE INDEX IF NOT EXISTS idx_commitments_person ON commitments(person_name);
CREATE INDEX IF NOT EXISTS idx_commitments_deadline ON commitments(deadline) WHERE status = 'open';
