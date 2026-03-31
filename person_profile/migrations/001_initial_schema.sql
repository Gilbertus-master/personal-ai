-- person_profile: Initial schema
-- 14 warstw profilowania osób + indeksy + widoki + audit log
-- Autor: Gilbertus Albans pipeline
-- Data: 2026-03-31

BEGIN;

-- ============================================================
-- Warstwa 0: Tożsamość (identity graph)
-- ============================================================

CREATE TABLE IF NOT EXISTS persons (
    person_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name     TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_me            BOOLEAN NOT NULL DEFAULT false,
    notes            TEXT,
    tags             TEXT[],
    gdpr_delete_requested_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS person_identities (
    identity_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id        UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,

    channel          TEXT NOT NULL,
    identifier       TEXT NOT NULL,
    display_name     TEXT,
    is_primary       BOOLEAN NOT NULL DEFAULT false,
    is_active        BOOLEAN NOT NULL DEFAULT true,

    match_type       TEXT NOT NULL DEFAULT 'manual',
    confidence       FLOAT NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    linked_by        TEXT,
    is_shared        BOOLEAN NOT NULL DEFAULT false,

    source_db        TEXT,
    source_record_id TEXT,

    first_seen_at    TIMESTAMPTZ,
    last_active_at   TIMESTAMPTZ,

    participant_ids  UUID[],

    superseded_by    UUID REFERENCES person_identities(identity_id),
    superseded_at    TIMESTAMPTZ,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(channel, identifier)
);

-- ============================================================
-- Warstwa 1: Demografika
-- ============================================================

CREATE TABLE IF NOT EXISTS person_demographics (
    person_id        UUID PRIMARY KEY REFERENCES persons(person_id) ON DELETE CASCADE,

    birth_year       SMALLINT,
    gender           TEXT,
    nationality      TEXT,
    native_language  TEXT,

    city             TEXT,
    country          TEXT,
    timezone         TEXT,
    coordinates      POINT,

    marital_status   TEXT,
    household_size   SMALLINT,
    education_level  TEXT,
    income_bracket   TEXT,
    housing_type     TEXT,

    confidence       FLOAT NOT NULL DEFAULT 1.0,
    source           TEXT NOT NULL DEFAULT 'manual',
    refreshed_at     TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Warstwa 2: Profil zawodowy
-- ============================================================

CREATE TABLE IF NOT EXISTS person_professional (
    person_id        UUID PRIMARY KEY REFERENCES persons(person_id) ON DELETE CASCADE,

    job_title        TEXT,
    company          TEXT,
    industry         TEXT,
    company_size     TEXT,
    seniority        TEXT,
    is_decision_maker BOOLEAN,

    career_history   JSONB,

    linkedin_url     TEXT,
    github_url       TEXT,
    personal_website TEXT,
    other_profiles   JSONB,

    job_change_detected_at TIMESTAMPTZ,
    job_change_source      TEXT,

    confidence       FLOAT NOT NULL DEFAULT 1.0,
    source           TEXT NOT NULL DEFAULT 'manual',
    refreshed_at     TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Warstwa 3: Behawioralna (agregaty)
-- ============================================================

CREATE TABLE IF NOT EXISTS person_behavioral (
    person_id              UUID PRIMARY KEY REFERENCES persons(person_id) ON DELETE CASCADE,

    total_interactions     INT NOT NULL DEFAULT 0,
    interactions_last_30d  INT NOT NULL DEFAULT 0,
    interactions_last_7d   INT NOT NULL DEFAULT 0,
    active_channels_count  SMALLINT NOT NULL DEFAULT 0,

    rfm_recency_days       INT,
    rfm_frequency_score    FLOAT,
    rfm_value_score        FLOAT,

    lead_score             FLOAT,
    churn_risk_score       FLOAT,
    engagement_score       FLOAT,

    clv_estimate           NUMERIC(12,2),
    clv_currency           TEXT DEFAULT 'PLN',

    first_interaction_at   TIMESTAMPTZ,
    last_interaction_at    TIMESTAMPTZ,
    computed_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Warstwa 4: Psychografika (AI-inferred)
-- ============================================================

CREATE TABLE IF NOT EXISTS person_psychographic (
    person_id            UUID PRIMARY KEY REFERENCES persons(person_id) ON DELETE CASCADE,

    big5_openness        FLOAT CHECK (big5_openness BETWEEN 0 AND 1),
    big5_conscientiousness FLOAT CHECK (big5_conscientiousness BETWEEN 0 AND 1),
    big5_extraversion    FLOAT CHECK (big5_extraversion BETWEEN 0 AND 1),
    big5_agreeableness   FLOAT CHECK (big5_agreeableness BETWEEN 0 AND 1),
    big5_neuroticism     FLOAT CHECK (big5_neuroticism BETWEEN 0 AND 1),

    values_list          TEXT[],
    interests_list       TEXT[],
    lifestyle_tags       TEXT[],

    risk_tolerance       TEXT,
    decision_style       TEXT,
    communication_style  TEXT,

    avg_sentiment        FLOAT,
    sentiment_variance   FLOAT,

    confidence           FLOAT NOT NULL DEFAULT 0.4,
    inferred_from        TEXT[],
    computed_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Warstwa 5: Social Graph (relacje)
-- ============================================================

CREATE TABLE IF NOT EXISTS person_relationships (
    rel_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id_from       UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    person_id_to         UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,

    tie_strength         FLOAT NOT NULL DEFAULT 0.0
                         CHECK (tie_strength BETWEEN -1.0 AND 1.0),

    dim_frequency        FLOAT NOT NULL DEFAULT 0.0,
    dim_recency          FLOAT NOT NULL DEFAULT 0.0,
    dim_reciprocity      FLOAT NOT NULL DEFAULT 0.0,
    dim_channel_div      FLOAT NOT NULL DEFAULT 0.0,
    dim_sentiment        FLOAT NOT NULL DEFAULT 0.0,
    dim_common_contacts  FLOAT NOT NULL DEFAULT 0.0,

    interaction_count    INT NOT NULL DEFAULT 0,
    initiated_by_from    INT NOT NULL DEFAULT 0,
    initiated_by_to      INT NOT NULL DEFAULT 0,

    dominant_channel     TEXT,
    relationship_types   TEXT[],
    first_contact_at     TIMESTAMPTZ,
    last_contact_at      TIMESTAMPTZ,

    is_manual_override   BOOLEAN NOT NULL DEFAULT false,
    manual_tie_strength  FLOAT,
    manual_types         TEXT[],
    computed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(person_id_from, person_id_to),
    CHECK (person_id_from <> person_id_to)
);

-- ============================================================
-- Warstwa 6: Otwarte pętle (open loops)
-- ============================================================

CREATE TABLE IF NOT EXISTS person_open_loops (
    loop_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id        UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,

    direction        TEXT NOT NULL,
    description      TEXT NOT NULL,
    context_channel  TEXT,
    source_message_ref TEXT,

    due_date         DATE,
    status           TEXT NOT NULL DEFAULT 'open',
    closed_at        TIMESTAMPTZ,
    close_note       TEXT,

    detected_by      TEXT NOT NULL DEFAULT 'manual',
    ai_confidence    FLOAT,
    reviewed_by_user BOOLEAN NOT NULL DEFAULT false,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Warstwa 7: Wzorzec komunikacji (communication DNA)
-- ============================================================

CREATE TABLE IF NOT EXISTS person_communication_pattern (
    person_id              UUID PRIMARY KEY REFERENCES persons(person_id) ON DELETE CASCADE,

    preferred_hours        INT[],
    preferred_days         INT[],
    avg_response_time_min  INT,
    response_time_by_channel JSONB,

    avg_message_length     INT,
    message_style          TEXT,
    formality_score        FLOAT,
    question_ratio         FLOAT,

    preferred_channel      TEXT,
    emergency_channel      TEXT,
    initiation_ratio       FLOAT,
    responds_to_cold       BOOLEAN,

    computed_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    computed_from_days     INT NOT NULL DEFAULT 90
);

-- ============================================================
-- Warstwa 8: Kontekst poznania (relationship origin)
-- ============================================================

CREATE TABLE IF NOT EXISTS person_origin (
    person_id         UUID PRIMARY KEY REFERENCES persons(person_id) ON DELETE CASCADE,

    origin_type       TEXT,
    origin_date       DATE,
    origin_context    TEXT,

    introduced_by     UUID[],
    introduction_note TEXT,

    first_topic       TEXT,
    first_channel     TEXT,

    shared_experiences JSONB,

    source            TEXT NOT NULL DEFAULT 'manual',
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Warstwa 9: Trajektoria relacji
-- ============================================================

CREATE TABLE IF NOT EXISTS person_relationship_trajectory (
    person_id              UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    person_id_to           UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,

    current_tie_strength   FLOAT NOT NULL,
    peak_tie_strength      FLOAT,
    peak_at                TIMESTAMPTZ,

    delta_7d               FLOAT,
    delta_30d              FLOAT,
    delta_90d              FLOAT,

    trajectory_status      TEXT NOT NULL DEFAULT 'stable',

    days_since_last_contact INT,
    history_snapshots      JSONB,

    computed_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (person_id, person_id_to)
);

-- ============================================================
-- Warstwa 10: Pozycja w sieci (network position)
-- ============================================================

CREATE TABLE IF NOT EXISTS person_network_position (
    person_id              UUID PRIMARY KEY REFERENCES persons(person_id) ON DELETE CASCADE,

    degree_centrality      INT NOT NULL DEFAULT 0,
    strong_ties_count      INT NOT NULL DEFAULT 0,
    weak_ties_count        INT NOT NULL DEFAULT 0,

    influence_score        FLOAT,
    is_broker              BOOLEAN NOT NULL DEFAULT false,
    broker_score           FLOAT,

    cluster_id             TEXT,
    cluster_label          TEXT,

    best_introducers       UUID[],

    computed_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Warstwa 11: Wspólne encje (shared context)
-- ============================================================

CREATE TABLE IF NOT EXISTS person_shared_context (
    context_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id      UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,

    entity_type    TEXT NOT NULL,
    entity_value   TEXT NOT NULL,
    relevance      FLOAT,
    first_seen_at  TIMESTAMPTZ,
    last_seen_at   TIMESTAMPTZ,
    source         TEXT NOT NULL DEFAULT 'ai_extracted',
    mention_count  INT NOT NULL DEFAULT 1
);

-- ============================================================
-- Warstwa 12: AI Briefing Card (cache)
-- ============================================================

CREATE TABLE IF NOT EXISTS person_briefings (
    briefing_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id      UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    perspective_id UUID REFERENCES persons(person_id),

    summary_text   TEXT NOT NULL,
    key_points     TEXT[],
    action_hints   TEXT[],

    trigger        TEXT NOT NULL DEFAULT 'scheduled',
    expires_at     TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '24 hours'),
    is_stale       BOOLEAN NOT NULL DEFAULT false,

    profile_hash   TEXT,

    generated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Warstwa 13: Next Best Action
-- ============================================================

CREATE TABLE IF NOT EXISTS person_next_actions (
    action_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id      UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,

    priority       SMALLINT NOT NULL DEFAULT 3,
    action_type    TEXT NOT NULL,

    title          TEXT NOT NULL,
    description    TEXT,
    suggested_text TEXT,
    suggested_channel TEXT,

    signal_source  TEXT NOT NULL,
    signal_data    JSONB,

    status         TEXT NOT NULL DEFAULT 'pending',
    snoozed_until  TIMESTAMPTZ,
    done_at        TIMESTAMPTZ,

    expires_at     TIMESTAMPTZ,
    generated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Warstwa 14: Pipeline state (delta update)
-- ============================================================

CREATE TABLE IF NOT EXISTS pipeline_state (
    source_name       TEXT PRIMARY KEY,
    last_run_at       TIMESTAMPTZ,
    last_success_at   TIMESTAMPTZ,
    records_processed INT NOT NULL DEFAULT 0,
    records_new       INT NOT NULL DEFAULT 0,
    records_updated   INT NOT NULL DEFAULT 0,
    records_skipped   INT NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'never_run',
    error_message     TEXT,
    run_duration_ms   INT,
    next_run_at       TIMESTAMPTZ
);

-- ============================================================
-- Audit trail
-- ============================================================

CREATE TABLE IF NOT EXISTS person_audit_log (
    audit_id       BIGSERIAL PRIMARY KEY,
    table_name     TEXT NOT NULL,
    record_id      TEXT NOT NULL,
    action         TEXT NOT NULL,  -- 'INSERT','UPDATE','DELETE'
    changed_fields JSONB,
    changed_by     TEXT NOT NULL DEFAULT 'system',
    changed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Indeksy
-- ============================================================

-- person_identities
CREATE INDEX IF NOT EXISTS idx_pi_person_id      ON person_identities(person_id);
CREATE INDEX IF NOT EXISTS idx_pi_channel_ident  ON person_identities(channel, identifier);
CREATE INDEX IF NOT EXISTS idx_pi_last_active    ON person_identities(last_active_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_pi_source_record  ON person_identities(source_db, source_record_id);

-- person_relationships
CREATE INDEX IF NOT EXISTS idx_pr_from           ON person_relationships(person_id_from);
CREATE INDEX IF NOT EXISTS idx_pr_to             ON person_relationships(person_id_to);
CREATE INDEX IF NOT EXISTS idx_pr_strength       ON person_relationships(tie_strength DESC);
CREATE INDEX IF NOT EXISTS idx_pr_last_contact   ON person_relationships(last_contact_at DESC NULLS LAST);

-- person_open_loops
CREATE INDEX IF NOT EXISTS idx_pol_person        ON person_open_loops(person_id);
CREATE INDEX IF NOT EXISTS idx_pol_status        ON person_open_loops(status) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_pol_due           ON person_open_loops(due_date) WHERE status = 'open';

-- person_next_actions
CREATE INDEX IF NOT EXISTS idx_pna_person        ON person_next_actions(person_id);
CREATE INDEX IF NOT EXISTS idx_pna_priority      ON person_next_actions(priority, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_pna_status        ON person_next_actions(status) WHERE status = 'pending';

-- person_shared_context
CREATE INDEX IF NOT EXISTS idx_psc_person        ON person_shared_context(person_id);
CREATE INDEX IF NOT EXISTS idx_psc_entity        ON person_shared_context(entity_type, entity_value);

-- person_briefings
CREATE INDEX IF NOT EXISTS idx_pb_person         ON person_briefings(person_id);
CREATE INDEX IF NOT EXISTS idx_pb_expires        ON person_briefings(expires_at) WHERE is_stale = false;

-- person_relationship_trajectory
CREATE INDEX IF NOT EXISTS idx_prt_to            ON person_relationship_trajectory(person_id_to);
CREATE INDEX IF NOT EXISTS idx_prt_status        ON person_relationship_trajectory(trajectory_status);

-- person_audit_log
CREATE INDEX IF NOT EXISTS idx_pal_table_record  ON person_audit_log(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_pal_changed_at    ON person_audit_log(changed_at DESC);

-- persons
CREATE INDEX IF NOT EXISTS idx_persons_is_me     ON persons(is_me) WHERE is_me = true;
CREATE INDEX IF NOT EXISTS idx_persons_gdpr      ON persons(gdpr_delete_requested_at)
    WHERE gdpr_delete_requested_at IS NOT NULL;

-- ============================================================
-- Widoki
-- ============================================================

CREATE OR REPLACE VIEW v_person_full AS
SELECT
    p.person_id,
    p.display_name,
    p.tags,
    p.notes,
    p.is_me,

    (SELECT jsonb_agg(jsonb_build_object(
        'channel', pi.channel,
        'identifier', pi.identifier,
        'display_name', pi.display_name,
        'is_primary', pi.is_primary,
        'is_active', pi.is_active,
        'confidence', pi.confidence,
        'match_type', pi.match_type,
        'last_active_at', pi.last_active_at
    ) ORDER BY pi.is_primary DESC, pi.last_active_at DESC NULLS LAST)
    FROM person_identities pi
    WHERE pi.person_id = p.person_id AND pi.is_active = true
    ) AS identities,

    pd.city, pd.country, pd.timezone, pd.birth_year,

    pp.job_title, pp.company, pp.industry, pp.seniority,
    pp.job_change_detected_at,

    pb.total_interactions, pb.last_interaction_at,
    pb.rfm_recency_days, pb.engagement_score,

    (SELECT pr.tie_strength FROM person_relationships pr
     JOIN persons me ON me.is_me = true
     WHERE pr.person_id_from = me.person_id AND pr.person_id_to = p.person_id
    ) AS my_tie_strength_to_them,

    (SELECT prt.trajectory_status FROM person_relationship_trajectory prt
     JOIN persons me ON me.is_me = true
     WHERE prt.person_id = me.person_id AND prt.person_id_to = p.person_id
    ) AS trajectory_status,

    (SELECT COUNT(*) FROM person_open_loops pol
     WHERE pol.person_id = p.person_id AND pol.status = 'open'
    ) AS open_loops_count,

    pnp.degree_centrality, pnp.influence_score,
    pnp.is_broker, pnp.cluster_label,

    p.created_at, p.updated_at

FROM persons p
LEFT JOIN person_demographics pd    ON pd.person_id = p.person_id
LEFT JOIN person_professional pp    ON pp.person_id = p.person_id
LEFT JOIN person_behavioral pb      ON pb.person_id = p.person_id
LEFT JOIN person_network_position pnp ON pnp.person_id = p.person_id
WHERE p.gdpr_delete_requested_at IS NULL;


CREATE OR REPLACE VIEW v_my_action_inbox AS
SELECT
    pna.action_id,
    pna.priority,
    pna.action_type,
    pna.title,
    pna.description,
    pna.suggested_text,
    pna.suggested_channel,
    pna.signal_source,
    p.person_id,
    p.display_name,
    p.tags,
    pp.job_title,
    pp.company,
    pna.expires_at,
    pna.generated_at
FROM person_next_actions pna
JOIN persons p ON p.person_id = pna.person_id
LEFT JOIN person_professional pp ON pp.person_id = p.person_id
WHERE pna.status = 'pending'
  AND (pna.snoozed_until IS NULL OR pna.snoozed_until < now())
  AND (pna.expires_at IS NULL OR pna.expires_at > now())
  AND p.gdpr_delete_requested_at IS NULL
ORDER BY pna.priority ASC, pna.generated_at DESC;


CREATE OR REPLACE VIEW v_relationship_spectrum AS
SELECT
    pr.person_id_from,
    pr.person_id_to,
    p.display_name AS contact_name,
    pp.job_title, pp.company,
    pr.tie_strength,
    pr.dim_frequency, pr.dim_recency, pr.dim_reciprocity,
    pr.dim_sentiment, pr.dim_channel_div, pr.dim_common_contacts,
    pr.relationship_types,
    pr.dominant_channel,
    pr.last_contact_at,
    prt.trajectory_status,
    prt.delta_30d,
    prt.days_since_last_contact,
    CASE
        WHEN pr.tie_strength >= 0.7  THEN 'bliska'
        WHEN pr.tie_strength >= 0.5  THEN 'silna'
        WHEN pr.tie_strength >= 0.3  THEN 'znajomość'
        WHEN pr.tie_strength >= 0.1  THEN 'słaba'
        WHEN pr.tie_strength >= -0.1 THEN 'neutralna'
        WHEN pr.tie_strength >= -0.3 THEN 'napięcie'
        ELSE 'konflikt'
    END AS strength_label
FROM person_relationships pr
JOIN persons p ON p.person_id = pr.person_id_to
LEFT JOIN person_professional pp ON pp.person_id = pr.person_id_to
LEFT JOIN person_relationship_trajectory prt
    ON prt.person_id = pr.person_id_from AND prt.person_id_to = pr.person_id_to
WHERE p.gdpr_delete_requested_at IS NULL;

COMMIT;
