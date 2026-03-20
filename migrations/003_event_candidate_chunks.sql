BEGIN;

CREATE TABLE IF NOT EXISTS event_candidate_chunks (
  chunk_id BIGINT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_candidate_chunks_reason
  ON event_candidate_chunks(reason);

COMMIT;
