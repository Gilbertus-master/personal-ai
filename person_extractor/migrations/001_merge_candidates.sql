-- merge_candidates: queue for manual identity resolution review
BEGIN;

CREATE TABLE IF NOT EXISTS merge_candidates (
    candidate_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id_a      UUID NOT NULL REFERENCES persons(person_id),
    person_id_b      UUID NOT NULL REFERENCES persons(person_id),
    similarity_score FLOAT NOT NULL,
    reason           TEXT,
    status           TEXT NOT NULL DEFAULT 'pending',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at      TIMESTAMPTZ,
    reviewed_by      TEXT,
    UNIQUE(person_id_a, person_id_b)
);

CREATE INDEX IF NOT EXISTS idx_mc_status ON merge_candidates(status) WHERE status = 'pending';

COMMIT;
