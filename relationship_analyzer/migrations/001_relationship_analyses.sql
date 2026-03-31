-- relationship_analyzer: relationship_analyses table + view + indexes
-- Stores per-perspective (a_to_b, b_to_a, dyadic) analysis results
-- Date: 2026-03-31

BEGIN;

CREATE TABLE IF NOT EXISTS relationship_analyses (
    analysis_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id_a              UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    person_id_b              UUID NOT NULL REFERENCES persons(person_id) ON DELETE CASCADE,
    perspective              TEXT NOT NULL CHECK (perspective IN ('a_to_b', 'b_to_a', 'dyadic')),

    -- P1: Behavioral
    interaction_count_total       INT,
    interaction_count_30d         INT,
    interaction_count_90d         INT,
    avg_interactions_per_week     FLOAT,
    days_since_last_contact       INT,
    longest_gap_days              INT,
    relationship_duration_days    INT,
    active_channels_count         SMALLINT,
    dominant_channel              TEXT,
    avg_message_length_chars      INT,
    response_time_avg_minutes     FLOAT,
    response_time_p90_minutes     FLOAT,

    -- P2: Asymmetry
    initiation_ratio              FLOAT,
    response_rate                 FLOAT,
    avg_lag_ego_minutes           FLOAT,
    avg_lag_alter_minutes         FLOAT,
    lag_asymmetry                 FLOAT,
    formality_score_ego           FLOAT,
    formality_score_alter         FLOAT,
    formality_asymmetry           FLOAT,

    -- P3: Sentiment
    avg_sentiment_ego             FLOAT,
    avg_sentiment_alter           FLOAT,
    sentiment_variance_ego        FLOAT,
    sentiment_trend               FLOAT,
    positive_signal_count         INT,
    negative_signal_count         INT,
    emotional_support_score       FLOAT,
    conflict_detected             BOOLEAN DEFAULT false,
    conflict_last_detected_at     TIMESTAMPTZ,

    -- P4: Topics
    top_topics                    TEXT[],
    topics_evolution              JSONB,
    shared_entities_count         INT,
    discussion_depth_score        FLOAT,

    -- P5: Trajectory
    trajectory_status             TEXT,
    tie_strength_current          FLOAT,
    tie_strength_delta_30d        FLOAT,
    tie_strength_delta_90d        FLOAT,
    peak_tie_strength             FLOAT,
    peak_tie_strength_at          TIMESTAMPTZ,
    lifecycle_stage               TEXT,
    turning_points                JSONB,

    -- P6: Style
    humor_signal_ratio            FLOAT,
    question_ratio_ego            FLOAT,
    personal_question_ratio       FLOAT,
    language_accommodation        FLOAT,
    emotional_language_ratio      FLOAT,
    support_language_ratio        FLOAT,
    communication_style_match     FLOAT,

    -- P7: Context
    first_contact_at              TIMESTAMPTZ,
    origin_type                   TEXT,
    origin_context                TEXT,
    shared_contacts_count         INT,
    open_loops_count              INT,
    shared_experiences_count      INT,
    milestone_count               INT,

    -- AI Synthesis
    health_score                  SMALLINT CHECK (health_score BETWEEN 0 AND 100),
    health_label                  TEXT,
    narrative_summary             TEXT,
    key_strengths                 TEXT[],
    key_risks                     TEXT[],
    opportunities                 TEXT[],
    recommended_action            TEXT,
    ai_model_used                 TEXT,
    ai_confidence                 FLOAT,

    -- Metadata
    data_window_days              INT NOT NULL DEFAULT 365,
    interactions_analyzed         INT,
    computed_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_stale                      BOOLEAN NOT NULL DEFAULT false,

    UNIQUE(person_id_a, person_id_b, perspective)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ra_person_a         ON relationship_analyses(person_id_a);
CREATE INDEX IF NOT EXISTS idx_ra_person_b         ON relationship_analyses(person_id_b);
CREATE INDEX IF NOT EXISTS idx_ra_health           ON relationship_analyses(health_score DESC) WHERE perspective = 'dyadic';
CREATE INDEX IF NOT EXISTS idx_ra_stale            ON relationship_analyses(is_stale) WHERE is_stale = true;
CREATE INDEX IF NOT EXISTS idx_ra_computed         ON relationship_analyses(computed_at DESC);
CREATE INDEX IF NOT EXISTS idx_ra_lifecycle        ON relationship_analyses(lifecycle_stage) WHERE perspective = 'dyadic';

-- View: top relationships from Sebastian's perspective
CREATE OR REPLACE VIEW v_my_top_relationships AS
SELECT
    ra.person_id_a,
    ra.person_id_b,
    pa.display_name AS name_a,
    pb.display_name AS name_b,
    pp.job_title,
    pp.company,
    ra.health_score,
    ra.health_label,
    ra.lifecycle_stage,
    ra.trajectory_status,
    ra.tie_strength_current,
    ra.interaction_count_total,
    ra.days_since_last_contact,
    ra.initiation_ratio,
    ra.avg_sentiment_ego,
    ra.open_loops_count,
    ra.narrative_summary,
    ra.key_strengths,
    ra.key_risks,
    ra.recommended_action,
    ra.computed_at
FROM relationship_analyses ra
JOIN persons pa ON pa.person_id = ra.person_id_a
JOIN persons pb ON pb.person_id = ra.person_id_b
LEFT JOIN person_professional pp ON pp.person_id = ra.person_id_b
WHERE ra.perspective = 'dyadic'
  AND pa.is_me = true
  AND pa.gdpr_delete_requested_at IS NULL
  AND pb.gdpr_delete_requested_at IS NULL
  AND ra.is_stale = false
ORDER BY ra.health_score DESC NULLS LAST;

COMMIT;
