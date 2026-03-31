BEGIN;

-- ============================================================
-- 1. process_events — unified event log from all sources
-- ============================================================
CREATE TABLE IF NOT EXISTS process_events (
    event_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source                  TEXT NOT NULL CHECK (source IN ('jira', 'crm', 'helpdesk', 'github', 'email')),
    entity_type             TEXT NOT NULL CHECK (entity_type IN ('ticket', 'deal', 'pr', 'email_thread')),
    entity_id               TEXT NOT NULL,
    from_state              TEXT,          -- NULL = entity was created
    to_state                TEXT NOT NULL,
    state_group             TEXT,
    actor_person_id         UUID REFERENCES persons(person_id),
    occurred_at             TIMESTAMPTZ NOT NULL,
    duration_in_prev_state_h FLOAT,
    context_tags            TEXT[],
    project_key             TEXT,
    priority                TEXT,
    raw_data                JSONB,
    collected_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pe_entity  ON process_events (entity_type, entity_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_pe_source  ON process_events (source, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_pe_actor   ON process_events (actor_person_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_pe_states  ON process_events (from_state, to_state, source);

-- ============================================================
-- 2. process_candidates — discovered patterns awaiting review
-- ============================================================
CREATE TABLE IF NOT EXISTS process_candidates (
    candidate_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_hash            TEXT NOT NULL UNIQUE,
    sequence                TEXT[] NOT NULL,
    source                  TEXT NOT NULL,
    entity_type             TEXT NOT NULL,
    project_keys            TEXT[],
    occurrences_count       INT NOT NULL,
    occurrences_per_week    FLOAT NOT NULL,
    avg_duration_h          FLOAT,
    p90_duration_h          FLOAT,
    unique_actors_count     INT,
    suggested_name          TEXT,
    suggested_description   TEXT,
    suggested_type          TEXT,
    suggested_metrics       JSONB,
    llm_confidence          FLOAT,
    status                  TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'approved', 'rejected', 'merged', 'snoozed')),
    merged_into_process_id  UUID REFERENCES processes(process_id),
    rejection_reason        TEXT,
    reviewed_by             UUID REFERENCES persons(person_id),
    reviewed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pc_status ON process_candidates (status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_pc_freq   ON process_candidates (occurrences_per_week DESC);

COMMIT;
