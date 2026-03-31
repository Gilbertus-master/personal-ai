"""Pydantic models for all 14 person_profile tables."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Warstwa 0: Tożsamość ──────────────────────────────────────────────

class Person(BaseModel):
    person_id: UUID = Field(default_factory=uuid4)
    display_name: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_me: bool = False
    notes: str | None = None
    tags: list[str] | None = None
    gdpr_delete_requested_at: datetime | None = None


class PersonIdentity(BaseModel):
    identity_id: UUID = Field(default_factory=uuid4)
    person_id: UUID

    channel: str
    identifier: str
    display_name: str | None = None
    is_primary: bool = False
    is_active: bool = True

    match_type: str = "manual"
    confidence: float = 1.0
    linked_by: str | None = None
    is_shared: bool = False

    source_db: str | None = None
    source_record_id: str | None = None

    first_seen_at: datetime | None = None
    last_active_at: datetime | None = None

    participant_ids: list[UUID] | None = None

    superseded_by: UUID | None = None
    superseded_at: datetime | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Warstwa 1: Demografika ────────────────────────────────────────────

class PersonDemographics(BaseModel):
    person_id: UUID

    birth_year: int | None = None
    gender: str | None = None
    nationality: str | None = None
    native_language: str | None = None

    city: str | None = None
    country: str | None = None
    timezone: str | None = None

    marital_status: str | None = None
    household_size: int | None = None
    education_level: str | None = None
    income_bracket: str | None = None
    housing_type: str | None = None

    confidence: float = 1.0
    source: str = "manual"
    refreshed_at: datetime | None = None
    updated_at: datetime | None = None


# ── Warstwa 2: Profil zawodowy ────────────────────────────────────────

class PersonProfessional(BaseModel):
    person_id: UUID

    job_title: str | None = None
    company: str | None = None
    industry: str | None = None
    company_size: str | None = None
    seniority: str | None = None
    is_decision_maker: bool | None = None

    career_history: list[dict[str, Any]] | None = None

    linkedin_url: str | None = None
    github_url: str | None = None
    personal_website: str | None = None
    other_profiles: dict[str, str] | None = None

    job_change_detected_at: datetime | None = None
    job_change_source: str | None = None

    confidence: float = 1.0
    source: str = "manual"
    refreshed_at: datetime | None = None
    updated_at: datetime | None = None


# ── Warstwa 3: Behawioralna ───────────────────────────────────────────

class PersonBehavioral(BaseModel):
    person_id: UUID

    total_interactions: int = 0
    interactions_last_30d: int = 0
    interactions_last_7d: int = 0
    active_channels_count: int = 0

    rfm_recency_days: int | None = None
    rfm_frequency_score: float | None = None
    rfm_value_score: float | None = None

    lead_score: float | None = None
    churn_risk_score: float | None = None
    engagement_score: float | None = None

    clv_estimate: float | None = None
    clv_currency: str = "PLN"

    first_interaction_at: datetime | None = None
    last_interaction_at: datetime | None = None
    computed_at: datetime | None = None


# ── Warstwa 4: Psychografika ─────────────────────────────────────────

class PersonPsychographic(BaseModel):
    person_id: UUID

    big5_openness: float | None = None
    big5_conscientiousness: float | None = None
    big5_extraversion: float | None = None
    big5_agreeableness: float | None = None
    big5_neuroticism: float | None = None

    values_list: list[str] | None = None
    interests_list: list[str] | None = None
    lifestyle_tags: list[str] | None = None

    risk_tolerance: str | None = None
    decision_style: str | None = None
    communication_style: str | None = None

    avg_sentiment: float | None = None
    sentiment_variance: float | None = None

    confidence: float = 0.4
    inferred_from: list[str] | None = None
    computed_at: datetime | None = None


# ── Warstwa 5: Social Graph ──────────────────────────────────────────

class PersonRelationship(BaseModel):
    rel_id: UUID = Field(default_factory=uuid4)
    person_id_from: UUID
    person_id_to: UUID

    tie_strength: float = 0.0

    dim_frequency: float = 0.0
    dim_recency: float = 0.0
    dim_reciprocity: float = 0.0
    dim_channel_div: float = 0.0
    dim_sentiment: float = 0.0
    dim_common_contacts: float = 0.0

    interaction_count: int = 0
    initiated_by_from: int = 0
    initiated_by_to: int = 0

    dominant_channel: str | None = None
    relationship_types: list[str] | None = None
    first_contact_at: datetime | None = None
    last_contact_at: datetime | None = None

    is_manual_override: bool = False
    manual_tie_strength: float | None = None
    manual_types: list[str] | None = None
    computed_at: datetime | None = None


# ── Warstwa 6: Open Loops ────────────────────────────────────────────

class PersonOpenLoop(BaseModel):
    loop_id: UUID = Field(default_factory=uuid4)
    person_id: UUID

    direction: str
    description: str
    context_channel: str | None = None
    source_message_ref: str | None = None

    due_date: date | None = None
    status: str = "open"
    closed_at: datetime | None = None
    close_note: str | None = None

    detected_by: str = "manual"
    ai_confidence: float | None = None
    reviewed_by_user: bool = False

    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Warstwa 7: Communication Pattern ─────────────────────────────────

class PersonCommunicationPattern(BaseModel):
    person_id: UUID

    preferred_hours: list[int] | None = None
    preferred_days: list[int] | None = None
    avg_response_time_min: int | None = None
    response_time_by_channel: dict[str, int] | None = None

    avg_message_length: int | None = None
    message_style: str | None = None
    formality_score: float | None = None
    question_ratio: float | None = None

    preferred_channel: str | None = None
    emergency_channel: str | None = None
    initiation_ratio: float | None = None
    responds_to_cold: bool | None = None

    computed_at: datetime | None = None
    computed_from_days: int = 90


# ── Warstwa 8: Origin ────────────────────────────────────────────────

class PersonOrigin(BaseModel):
    person_id: UUID

    origin_type: str | None = None
    origin_date: date | None = None
    origin_context: str | None = None

    introduced_by: list[UUID] | None = None
    introduction_note: str | None = None

    first_topic: str | None = None
    first_channel: str | None = None

    shared_experiences: list[dict[str, str]] | None = None

    source: str = "manual"
    updated_at: datetime | None = None


# ── Warstwa 9: Trajectory ────────────────────────────────────────────

class PersonRelationshipTrajectory(BaseModel):
    person_id: UUID
    person_id_to: UUID

    current_tie_strength: float
    peak_tie_strength: float | None = None
    peak_at: datetime | None = None

    delta_7d: float | None = None
    delta_30d: float | None = None
    delta_90d: float | None = None

    trajectory_status: str = "stable"

    days_since_last_contact: int | None = None
    history_snapshots: list[dict[str, Any]] | None = None

    computed_at: datetime | None = None


# ── Warstwa 10: Network Position ─────────────────────────────────────

class PersonNetworkPosition(BaseModel):
    person_id: UUID

    degree_centrality: int = 0
    strong_ties_count: int = 0
    weak_ties_count: int = 0

    influence_score: float | None = None
    is_broker: bool = False
    broker_score: float | None = None

    cluster_id: str | None = None
    cluster_label: str | None = None

    best_introducers: list[UUID] | None = None

    computed_at: datetime | None = None


# ── Warstwa 11: Shared Context ───────────────────────────────────────

class PersonSharedContext(BaseModel):
    context_id: UUID = Field(default_factory=uuid4)
    person_id: UUID

    entity_type: str
    entity_value: str
    relevance: float | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    source: str = "ai_extracted"
    mention_count: int = 1


# ── Warstwa 12: Briefing Card ────────────────────────────────────────

class PersonBriefing(BaseModel):
    briefing_id: UUID = Field(default_factory=uuid4)
    person_id: UUID
    perspective_id: UUID | None = None

    summary_text: str
    key_points: list[str] | None = None
    action_hints: list[str] | None = None

    trigger: str = "scheduled"
    expires_at: datetime | None = None
    is_stale: bool = False

    profile_hash: str | None = None
    generated_at: datetime | None = None


# ── Warstwa 13: Next Best Action ─────────────────────────────────────

class PersonNextAction(BaseModel):
    action_id: UUID = Field(default_factory=uuid4)
    person_id: UUID

    priority: int = 3
    action_type: str

    title: str
    description: str | None = None
    suggested_text: str | None = None
    suggested_channel: str | None = None

    signal_source: str
    signal_data: dict[str, Any] | None = None

    status: str = "pending"
    snoozed_until: datetime | None = None
    done_at: datetime | None = None

    expires_at: datetime | None = None
    generated_at: datetime | None = None


# ── Warstwa 14: Pipeline State ───────────────────────────────────────

class PipelineState(BaseModel):
    source_name: str
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    records_processed: int = 0
    records_new: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    status: str = "never_run"
    error_message: str | None = None
    run_duration_ms: int | None = None
    next_run_at: datetime | None = None
