"""CRUD operations for all person_profile tables.

Uses the shared connection pool from app.db.postgres.
All SQL queries are parameterized.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row


from .models import (
    Person,
    PersonBehavioral,
    PersonBriefing,
    PersonCommunicationPattern,
    PersonDemographics,
    PersonIdentity,
    PersonNextAction,
    PersonOpenLoop,
    PersonOrigin,
    PersonProfessional,
    PersonPsychographic,
    PersonRelationship,
    PersonRelationshipTrajectory,
    PersonNetworkPosition,
    PersonSharedContext,
)

log = structlog.get_logger("person_profile.repository")


# ─── Helpers ──────────────────────────────────────────────────────────

def _json_default(obj: Any) -> Any:
    if isinstance(obj, (UUID, datetime)):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _to_json(val: Any) -> str | None:
    if val is None:
        return None
    return json.dumps(val, default=_json_default, ensure_ascii=False)


def _uuid_list(val: list[UUID] | None) -> list[str] | None:
    if val is None:
        return None
    return [str(u) for u in val]


def _audit_log(
    conn: psycopg.Connection,
    table_name: str,
    record_id: str,
    action: str,
    changed_fields: dict | None = None,
    changed_by: str = "system",
) -> None:
    conn.execute(
        """INSERT INTO person_audit_log
           (table_name, record_id, action, changed_fields, changed_by)
           VALUES (%s, %s, %s, %s, %s)""",
        (table_name, record_id, action, _to_json(changed_fields), changed_by),
    )


# ═══════════════════════════════════════════════════════════════════════
# Persons (Warstwa 0)
# ═══════════════════════════════════════════════════════════════════════

def upsert_person(conn: psycopg.Connection, p: Person) -> UUID:
    row = conn.execute(
        """INSERT INTO persons
           (person_id, display_name, is_me, notes, tags, gdpr_delete_requested_at)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (person_id) DO UPDATE SET
               display_name = EXCLUDED.display_name,
               notes = EXCLUDED.notes,
               tags = EXCLUDED.tags,
               gdpr_delete_requested_at = EXCLUDED.gdpr_delete_requested_at,
               updated_at = now()
           RETURNING person_id""",
        (
            str(p.person_id), p.display_name, p.is_me,
            p.notes, p.tags, p.gdpr_delete_requested_at,
        ),
    ).fetchone()
    pid = row[0]
    _audit_log(conn, "persons", str(pid), "UPSERT")
    return pid


def get_person(conn: psycopg.Connection, person_id: UUID) -> dict | None:
    conn.row_factory = dict_row
    return conn.execute(
        "SELECT * FROM persons WHERE person_id = %s", (str(person_id),)
    ).fetchone()


def get_me(conn: psycopg.Connection) -> dict | None:
    conn.row_factory = dict_row
    return conn.execute(
        "SELECT * FROM persons WHERE is_me = true LIMIT 1"
    ).fetchone()


def list_persons(
    conn: psycopg.Connection,
    limit: int = 100,
    offset: int = 0,
    tags: list[str] | None = None,
) -> list[dict]:
    conn.row_factory = dict_row
    if tags:
        return conn.execute(
            """SELECT * FROM persons
               WHERE gdpr_delete_requested_at IS NULL AND tags && %s
               ORDER BY updated_at DESC LIMIT %s OFFSET %s""",
            (tags, limit, offset),
        ).fetchall()
    return conn.execute(
        """SELECT * FROM persons
           WHERE gdpr_delete_requested_at IS NULL
           ORDER BY updated_at DESC LIMIT %s OFFSET %s""",
        (limit, offset),
    ).fetchall()


def delete_person(conn: psycopg.Connection, person_id: UUID) -> None:
    conn.execute(
        "DELETE FROM persons WHERE person_id = %s", (str(person_id),)
    )
    _audit_log(conn, "persons", str(person_id), "DELETE")


def anonymize_person(conn: psycopg.Connection, person_id: UUID) -> None:
    """GDPR soft-delete: clear PII but keep aggregates."""
    pid = str(person_id)
    conn.execute(
        """UPDATE persons SET
               display_name = 'ANONYMIZED',
               notes = NULL,
               tags = NULL,
               gdpr_delete_requested_at = now(),
               updated_at = now()
           WHERE person_id = %s""",
        (pid,),
    )
    conn.execute(
        """UPDATE person_identities SET
               identifier = 'ANONYMIZED',
               display_name = NULL,
               is_active = false,
               updated_at = now()
           WHERE person_id = %s""",
        (pid,),
    )
    conn.execute(
        """UPDATE person_demographics SET
               city = NULL, country = NULL, nationality = NULL,
               native_language = NULL, updated_at = now()
           WHERE person_id = %s""",
        (pid,),
    )
    conn.execute(
        """UPDATE person_professional SET
               job_title = NULL, company = NULL,
               linkedin_url = NULL, github_url = NULL,
               personal_website = NULL, other_profiles = NULL,
               updated_at = now()
           WHERE person_id = %s""",
        (pid,),
    )
    conn.execute(
        "DELETE FROM person_origin WHERE person_id = %s", (pid,)
    )
    _audit_log(conn, "persons", pid, "ANONYMIZE")


# ═══════════════════════════════════════════════════════════════════════
# Person Identities (Warstwa 0)
# ═══════════════════════════════════════════════════════════════════════

def upsert_identity(conn: psycopg.Connection, i: PersonIdentity) -> UUID:
    row = conn.execute(
        """INSERT INTO person_identities
           (identity_id, person_id, channel, identifier, display_name,
            is_primary, is_active, match_type, confidence, linked_by,
            is_shared, source_db, source_record_id,
            first_seen_at, last_active_at, participant_ids,
            superseded_by, superseded_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (channel, identifier) DO UPDATE SET
               person_id = EXCLUDED.person_id,
               display_name = EXCLUDED.display_name,
               is_primary = EXCLUDED.is_primary,
               is_active = EXCLUDED.is_active,
               confidence = EXCLUDED.confidence,
               last_active_at = EXCLUDED.last_active_at,
               participant_ids = EXCLUDED.participant_ids,
               updated_at = now()
           RETURNING identity_id""",
        (
            str(i.identity_id), str(i.person_id), i.channel, i.identifier,
            i.display_name, i.is_primary, i.is_active,
            i.match_type, i.confidence, i.linked_by,
            i.is_shared, i.source_db, i.source_record_id,
            i.first_seen_at, i.last_active_at, _uuid_list(i.participant_ids),
            str(i.superseded_by) if i.superseded_by else None, i.superseded_at,
        ),
    ).fetchone()
    return row[0]


def get_identities(conn: psycopg.Connection, person_id: UUID) -> list[dict]:
    conn.row_factory = dict_row
    return conn.execute(
        """SELECT * FROM person_identities
           WHERE person_id = %s AND is_active = true
           ORDER BY is_primary DESC, last_active_at DESC NULLS LAST""",
        (str(person_id),),
    ).fetchall()


def find_person_by_identifier(
    conn: psycopg.Connection, channel: str, identifier: str
) -> dict | None:
    conn.row_factory = dict_row
    return conn.execute(
        """SELECT pi.*, p.display_name AS person_display_name
           FROM person_identities pi
           JOIN persons p ON p.person_id = pi.person_id
           WHERE pi.channel = %s AND pi.identifier = %s""",
        (channel, identifier),
    ).fetchone()


# ═══════════════════════════════════════════════════════════════════════
# Demographics (Warstwa 1)
# ═══════════════════════════════════════════════════════════════════════

def upsert_demographics(conn: psycopg.Connection, d: PersonDemographics) -> None:
    conn.execute(
        """INSERT INTO person_demographics
           (person_id, birth_year, gender, nationality, native_language,
            city, country, timezone,
            marital_status, household_size, education_level,
            income_bracket, housing_type,
            confidence, source, refreshed_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (person_id) DO UPDATE SET
               birth_year = EXCLUDED.birth_year,
               gender = EXCLUDED.gender,
               nationality = EXCLUDED.nationality,
               native_language = EXCLUDED.native_language,
               city = EXCLUDED.city,
               country = EXCLUDED.country,
               timezone = EXCLUDED.timezone,
               marital_status = EXCLUDED.marital_status,
               household_size = EXCLUDED.household_size,
               education_level = EXCLUDED.education_level,
               income_bracket = EXCLUDED.income_bracket,
               housing_type = EXCLUDED.housing_type,
               confidence = EXCLUDED.confidence,
               source = EXCLUDED.source,
               refreshed_at = EXCLUDED.refreshed_at,
               updated_at = now()""",
        (
            str(d.person_id), d.birth_year, d.gender, d.nationality,
            d.native_language, d.city, d.country, d.timezone,
            d.marital_status, d.household_size, d.education_level,
            d.income_bracket, d.housing_type,
            d.confidence, d.source, d.refreshed_at,
        ),
    )


def get_demographics(conn: psycopg.Connection, person_id: UUID) -> dict | None:
    conn.row_factory = dict_row
    return conn.execute(
        "SELECT * FROM person_demographics WHERE person_id = %s",
        (str(person_id),),
    ).fetchone()


# ═══════════════════════════════════════════════════════════════════════
# Professional (Warstwa 2)
# ═══════════════════════════════════════════════════════════════════════

def upsert_professional(conn: psycopg.Connection, p: PersonProfessional) -> None:
    conn.execute(
        """INSERT INTO person_professional
           (person_id, job_title, company, industry, company_size,
            seniority, is_decision_maker, career_history,
            linkedin_url, github_url, personal_website, other_profiles,
            job_change_detected_at, job_change_source,
            confidence, source, refreshed_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (person_id) DO UPDATE SET
               job_title = EXCLUDED.job_title,
               company = EXCLUDED.company,
               industry = EXCLUDED.industry,
               company_size = EXCLUDED.company_size,
               seniority = EXCLUDED.seniority,
               is_decision_maker = EXCLUDED.is_decision_maker,
               career_history = EXCLUDED.career_history,
               linkedin_url = EXCLUDED.linkedin_url,
               github_url = EXCLUDED.github_url,
               personal_website = EXCLUDED.personal_website,
               other_profiles = EXCLUDED.other_profiles,
               job_change_detected_at = EXCLUDED.job_change_detected_at,
               job_change_source = EXCLUDED.job_change_source,
               confidence = EXCLUDED.confidence,
               source = EXCLUDED.source,
               refreshed_at = EXCLUDED.refreshed_at,
               updated_at = now()""",
        (
            str(p.person_id), p.job_title, p.company, p.industry,
            p.company_size, p.seniority, p.is_decision_maker,
            _to_json(p.career_history),
            p.linkedin_url, p.github_url, p.personal_website,
            _to_json(p.other_profiles),
            p.job_change_detected_at, p.job_change_source,
            p.confidence, p.source, p.refreshed_at,
        ),
    )


def get_professional(conn: psycopg.Connection, person_id: UUID) -> dict | None:
    conn.row_factory = dict_row
    return conn.execute(
        "SELECT * FROM person_professional WHERE person_id = %s",
        (str(person_id),),
    ).fetchone()


# ═══════════════════════════════════════════════════════════════════════
# Behavioral (Warstwa 3)
# ═══════════════════════════════════════════════════════════════════════

def upsert_behavioral(conn: psycopg.Connection, b: PersonBehavioral) -> None:
    conn.execute(
        """INSERT INTO person_behavioral
           (person_id, total_interactions, interactions_last_30d,
            interactions_last_7d, active_channels_count,
            rfm_recency_days, rfm_frequency_score, rfm_value_score,
            lead_score, churn_risk_score, engagement_score,
            clv_estimate, clv_currency,
            first_interaction_at, last_interaction_at, computed_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
           ON CONFLICT (person_id) DO UPDATE SET
               total_interactions = EXCLUDED.total_interactions,
               interactions_last_30d = EXCLUDED.interactions_last_30d,
               interactions_last_7d = EXCLUDED.interactions_last_7d,
               active_channels_count = EXCLUDED.active_channels_count,
               rfm_recency_days = EXCLUDED.rfm_recency_days,
               rfm_frequency_score = EXCLUDED.rfm_frequency_score,
               rfm_value_score = EXCLUDED.rfm_value_score,
               lead_score = EXCLUDED.lead_score,
               churn_risk_score = EXCLUDED.churn_risk_score,
               engagement_score = EXCLUDED.engagement_score,
               clv_estimate = EXCLUDED.clv_estimate,
               clv_currency = EXCLUDED.clv_currency,
               first_interaction_at = EXCLUDED.first_interaction_at,
               last_interaction_at = EXCLUDED.last_interaction_at,
               computed_at = now()""",
        (
            str(b.person_id), b.total_interactions, b.interactions_last_30d,
            b.interactions_last_7d, b.active_channels_count,
            b.rfm_recency_days, b.rfm_frequency_score, b.rfm_value_score,
            b.lead_score, b.churn_risk_score, b.engagement_score,
            b.clv_estimate, b.clv_currency,
            b.first_interaction_at, b.last_interaction_at,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Psychographic (Warstwa 4)
# ═══════════════════════════════════════════════════════════════════════

def upsert_psychographic(conn: psycopg.Connection, p: PersonPsychographic) -> None:
    conn.execute(
        """INSERT INTO person_psychographic
           (person_id, big5_openness, big5_conscientiousness,
            big5_extraversion, big5_agreeableness, big5_neuroticism,
            values_list, interests_list, lifestyle_tags,
            risk_tolerance, decision_style, communication_style,
            avg_sentiment, sentiment_variance,
            confidence, inferred_from, computed_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
           ON CONFLICT (person_id) DO UPDATE SET
               big5_openness = EXCLUDED.big5_openness,
               big5_conscientiousness = EXCLUDED.big5_conscientiousness,
               big5_extraversion = EXCLUDED.big5_extraversion,
               big5_agreeableness = EXCLUDED.big5_agreeableness,
               big5_neuroticism = EXCLUDED.big5_neuroticism,
               values_list = EXCLUDED.values_list,
               interests_list = EXCLUDED.interests_list,
               lifestyle_tags = EXCLUDED.lifestyle_tags,
               risk_tolerance = EXCLUDED.risk_tolerance,
               decision_style = EXCLUDED.decision_style,
               communication_style = EXCLUDED.communication_style,
               avg_sentiment = EXCLUDED.avg_sentiment,
               sentiment_variance = EXCLUDED.sentiment_variance,
               confidence = EXCLUDED.confidence,
               inferred_from = EXCLUDED.inferred_from,
               computed_at = now()""",
        (
            str(p.person_id), p.big5_openness, p.big5_conscientiousness,
            p.big5_extraversion, p.big5_agreeableness, p.big5_neuroticism,
            p.values_list, p.interests_list, p.lifestyle_tags,
            p.risk_tolerance, p.decision_style, p.communication_style,
            p.avg_sentiment, p.sentiment_variance,
            p.confidence, p.inferred_from,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Relationships (Warstwa 5)
# ═══════════════════════════════════════════════════════════════════════

def upsert_relationship(conn: psycopg.Connection, r: PersonRelationship) -> UUID:
    row = conn.execute(
        """INSERT INTO person_relationships
           (rel_id, person_id_from, person_id_to, tie_strength,
            dim_frequency, dim_recency, dim_reciprocity,
            dim_channel_div, dim_sentiment, dim_common_contacts,
            interaction_count, initiated_by_from, initiated_by_to,
            dominant_channel, relationship_types,
            first_contact_at, last_contact_at,
            is_manual_override, manual_tie_strength, manual_types,
            computed_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
           ON CONFLICT (person_id_from, person_id_to) DO UPDATE SET
               tie_strength = CASE
                   WHEN person_relationships.is_manual_override THEN person_relationships.tie_strength
                   ELSE EXCLUDED.tie_strength END,
               dim_frequency = EXCLUDED.dim_frequency,
               dim_recency = EXCLUDED.dim_recency,
               dim_reciprocity = EXCLUDED.dim_reciprocity,
               dim_channel_div = EXCLUDED.dim_channel_div,
               dim_sentiment = EXCLUDED.dim_sentiment,
               dim_common_contacts = EXCLUDED.dim_common_contacts,
               interaction_count = EXCLUDED.interaction_count,
               initiated_by_from = EXCLUDED.initiated_by_from,
               initiated_by_to = EXCLUDED.initiated_by_to,
               dominant_channel = EXCLUDED.dominant_channel,
               relationship_types = EXCLUDED.relationship_types,
               first_contact_at = LEAST(person_relationships.first_contact_at, EXCLUDED.first_contact_at),
               last_contact_at = GREATEST(person_relationships.last_contact_at, EXCLUDED.last_contact_at),
               computed_at = now()
           RETURNING rel_id""",
        (
            str(r.rel_id), str(r.person_id_from), str(r.person_id_to),
            r.tie_strength,
            r.dim_frequency, r.dim_recency, r.dim_reciprocity,
            r.dim_channel_div, r.dim_sentiment, r.dim_common_contacts,
            r.interaction_count, r.initiated_by_from, r.initiated_by_to,
            r.dominant_channel, r.relationship_types,
            r.first_contact_at, r.last_contact_at,
            r.is_manual_override, r.manual_tie_strength, r.manual_types,
        ),
    ).fetchone()
    return row[0]


def get_relationships(
    conn: psycopg.Connection,
    person_id: UUID,
    min_strength: float = -1.0,
) -> list[dict]:
    conn.row_factory = dict_row
    return conn.execute(
        """SELECT * FROM person_relationships
           WHERE person_id_from = %s AND tie_strength >= %s
           ORDER BY tie_strength DESC""",
        (str(person_id), min_strength),
    ).fetchall()


def get_relationship_pair(
    conn: psycopg.Connection, from_id: UUID, to_id: UUID
) -> dict | None:
    conn.row_factory = dict_row
    return conn.execute(
        """SELECT * FROM person_relationships
           WHERE person_id_from = %s AND person_id_to = %s""",
        (str(from_id), str(to_id)),
    ).fetchone()


# ═══════════════════════════════════════════════════════════════════════
# Open Loops (Warstwa 6)
# ═══════════════════════════════════════════════════════════════════════

def insert_open_loop(conn: psycopg.Connection, ol: PersonOpenLoop) -> UUID:
    row = conn.execute(
        """INSERT INTO person_open_loops
           (loop_id, person_id, direction, description,
            context_channel, source_message_ref,
            due_date, status, detected_by, ai_confidence, reviewed_by_user)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING loop_id""",
        (
            str(ol.loop_id), str(ol.person_id), ol.direction, ol.description,
            ol.context_channel, ol.source_message_ref,
            ol.due_date, ol.status, ol.detected_by, ol.ai_confidence,
            ol.reviewed_by_user,
        ),
    ).fetchone()
    return row[0]


def close_open_loop(
    conn: psycopg.Connection, loop_id: UUID, close_note: str | None = None
) -> None:
    conn.execute(
        """UPDATE person_open_loops SET
               status = 'closed', closed_at = now(),
               close_note = %s, updated_at = now()
           WHERE loop_id = %s""",
        (close_note, str(loop_id)),
    )


def get_open_loops(
    conn: psycopg.Connection,
    person_id: UUID | None = None,
    status: str = "open",
) -> list[dict]:
    conn.row_factory = dict_row
    if person_id:
        return conn.execute(
            """SELECT * FROM person_open_loops
               WHERE person_id = %s AND status = %s
               ORDER BY due_date ASC NULLS LAST""",
            (str(person_id), status),
        ).fetchall()
    return conn.execute(
        """SELECT * FROM person_open_loops WHERE status = %s
           ORDER BY due_date ASC NULLS LAST""",
        (status,),
    ).fetchall()


# ═══════════════════════════════════════════════════════════════════════
# Communication Pattern (Warstwa 7)
# ═══════════════════════════════════════════════════════════════════════

def upsert_communication_pattern(
    conn: psycopg.Connection, cp: PersonCommunicationPattern
) -> None:
    conn.execute(
        """INSERT INTO person_communication_pattern
           (person_id, preferred_hours, preferred_days,
            avg_response_time_min, response_time_by_channel,
            avg_message_length, message_style, formality_score,
            question_ratio, preferred_channel, emergency_channel,
            initiation_ratio, responds_to_cold,
            computed_at, computed_from_days)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),%s)
           ON CONFLICT (person_id) DO UPDATE SET
               preferred_hours = EXCLUDED.preferred_hours,
               preferred_days = EXCLUDED.preferred_days,
               avg_response_time_min = EXCLUDED.avg_response_time_min,
               response_time_by_channel = EXCLUDED.response_time_by_channel,
               avg_message_length = EXCLUDED.avg_message_length,
               message_style = EXCLUDED.message_style,
               formality_score = EXCLUDED.formality_score,
               question_ratio = EXCLUDED.question_ratio,
               preferred_channel = EXCLUDED.preferred_channel,
               emergency_channel = EXCLUDED.emergency_channel,
               initiation_ratio = EXCLUDED.initiation_ratio,
               responds_to_cold = EXCLUDED.responds_to_cold,
               computed_at = now(),
               computed_from_days = EXCLUDED.computed_from_days""",
        (
            str(cp.person_id), cp.preferred_hours, cp.preferred_days,
            cp.avg_response_time_min, _to_json(cp.response_time_by_channel),
            cp.avg_message_length, cp.message_style, cp.formality_score,
            cp.question_ratio, cp.preferred_channel, cp.emergency_channel,
            cp.initiation_ratio, cp.responds_to_cold,
            cp.computed_from_days,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Origin (Warstwa 8)
# ═══════════════════════════════════════════════════════════════════════

def upsert_origin(conn: psycopg.Connection, o: PersonOrigin) -> None:
    conn.execute(
        """INSERT INTO person_origin
           (person_id, origin_type, origin_date, origin_context,
            introduced_by, introduction_note,
            first_topic, first_channel, shared_experiences, source)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (person_id) DO UPDATE SET
               origin_type = EXCLUDED.origin_type,
               origin_date = EXCLUDED.origin_date,
               origin_context = EXCLUDED.origin_context,
               introduced_by = EXCLUDED.introduced_by,
               introduction_note = EXCLUDED.introduction_note,
               first_topic = EXCLUDED.first_topic,
               first_channel = EXCLUDED.first_channel,
               shared_experiences = EXCLUDED.shared_experiences,
               source = EXCLUDED.source,
               updated_at = now()""",
        (
            str(o.person_id), o.origin_type, o.origin_date, o.origin_context,
            _uuid_list(o.introduced_by), o.introduction_note,
            o.first_topic, o.first_channel, _to_json(o.shared_experiences),
            o.source,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Trajectory (Warstwa 9)
# ═══════════════════════════════════════════════════════════════════════

def upsert_trajectory(
    conn: psycopg.Connection, t: PersonRelationshipTrajectory
) -> None:
    conn.execute(
        """INSERT INTO person_relationship_trajectory
           (person_id, person_id_to, current_tie_strength,
            peak_tie_strength, peak_at,
            delta_7d, delta_30d, delta_90d,
            trajectory_status, days_since_last_contact,
            history_snapshots, computed_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
           ON CONFLICT (person_id, person_id_to) DO UPDATE SET
               current_tie_strength = EXCLUDED.current_tie_strength,
               peak_tie_strength = GREATEST(
                   person_relationship_trajectory.peak_tie_strength,
                   EXCLUDED.current_tie_strength),
               peak_at = CASE
                   WHEN EXCLUDED.current_tie_strength >
                        COALESCE(person_relationship_trajectory.peak_tie_strength, 0)
                   THEN now() ELSE person_relationship_trajectory.peak_at END,
               delta_7d = EXCLUDED.delta_7d,
               delta_30d = EXCLUDED.delta_30d,
               delta_90d = EXCLUDED.delta_90d,
               trajectory_status = EXCLUDED.trajectory_status,
               days_since_last_contact = EXCLUDED.days_since_last_contact,
               history_snapshots = EXCLUDED.history_snapshots,
               computed_at = now()""",
        (
            str(t.person_id), str(t.person_id_to), t.current_tie_strength,
            t.peak_tie_strength, t.peak_at,
            t.delta_7d, t.delta_30d, t.delta_90d,
            t.trajectory_status, t.days_since_last_contact,
            _to_json(t.history_snapshots),
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Network Position (Warstwa 10)
# ═══════════════════════════════════════════════════════════════════════

def upsert_network_position(
    conn: psycopg.Connection, np: PersonNetworkPosition
) -> None:
    conn.execute(
        """INSERT INTO person_network_position
           (person_id, degree_centrality, strong_ties_count, weak_ties_count,
            influence_score, is_broker, broker_score,
            cluster_id, cluster_label, best_introducers, computed_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
           ON CONFLICT (person_id) DO UPDATE SET
               degree_centrality = EXCLUDED.degree_centrality,
               strong_ties_count = EXCLUDED.strong_ties_count,
               weak_ties_count = EXCLUDED.weak_ties_count,
               influence_score = EXCLUDED.influence_score,
               is_broker = EXCLUDED.is_broker,
               broker_score = EXCLUDED.broker_score,
               cluster_id = EXCLUDED.cluster_id,
               cluster_label = EXCLUDED.cluster_label,
               best_introducers = EXCLUDED.best_introducers,
               computed_at = now()""",
        (
            str(np.person_id), np.degree_centrality,
            np.strong_ties_count, np.weak_ties_count,
            np.influence_score, np.is_broker, np.broker_score,
            np.cluster_id, np.cluster_label, _uuid_list(np.best_introducers),
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Shared Context (Warstwa 11)
# ═══════════════════════════════════════════════════════════════════════

def upsert_shared_context(conn: psycopg.Connection, sc: PersonSharedContext) -> UUID:
    row = conn.execute(
        """INSERT INTO person_shared_context
           (context_id, person_id, entity_type, entity_value,
            relevance, first_seen_at, last_seen_at, source, mention_count)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (context_id) DO UPDATE SET
               relevance = EXCLUDED.relevance,
               last_seen_at = EXCLUDED.last_seen_at,
               mention_count = person_shared_context.mention_count + 1
           RETURNING context_id""",
        (
            str(sc.context_id), str(sc.person_id), sc.entity_type,
            sc.entity_value, sc.relevance, sc.first_seen_at,
            sc.last_seen_at, sc.source, sc.mention_count,
        ),
    ).fetchone()
    return row[0]


def get_shared_contexts(
    conn: psycopg.Connection, person_id: UUID
) -> list[dict]:
    conn.row_factory = dict_row
    return conn.execute(
        """SELECT * FROM person_shared_context
           WHERE person_id = %s ORDER BY relevance DESC NULLS LAST""",
        (str(person_id),),
    ).fetchall()


# ═══════════════════════════════════════════════════════════════════════
# Briefings (Warstwa 12)
# ═══════════════════════════════════════════════════════════════════════

def insert_briefing(conn: psycopg.Connection, b: PersonBriefing) -> UUID:
    row = conn.execute(
        """INSERT INTO person_briefings
           (briefing_id, person_id, perspective_id,
            summary_text, key_points, action_hints,
            trigger, expires_at, is_stale, profile_hash)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING briefing_id""",
        (
            str(b.briefing_id), str(b.person_id),
            str(b.perspective_id) if b.perspective_id else None,
            b.summary_text, b.key_points, b.action_hints,
            b.trigger, b.expires_at, b.is_stale, b.profile_hash,
        ),
    ).fetchone()
    return row[0]


def get_fresh_briefing(
    conn: psycopg.Connection, person_id: UUID
) -> dict | None:
    conn.row_factory = dict_row
    return conn.execute(
        """SELECT * FROM person_briefings
           WHERE person_id = %s AND is_stale = false
             AND expires_at > now()
           ORDER BY generated_at DESC LIMIT 1""",
        (str(person_id),),
    ).fetchone()


def mark_briefings_stale(conn: psycopg.Connection, person_id: UUID) -> int:
    cur = conn.execute(
        """UPDATE person_briefings SET is_stale = true
           WHERE person_id = %s AND is_stale = false""",
        (str(person_id),),
    )
    return cur.rowcount


# ═══════════════════════════════════════════════════════════════════════
# Next Actions (Warstwa 13)
# ═══════════════════════════════════════════════════════════════════════

def insert_next_action(conn: psycopg.Connection, a: PersonNextAction) -> UUID:
    row = conn.execute(
        """INSERT INTO person_next_actions
           (action_id, person_id, priority, action_type,
            title, description, suggested_text, suggested_channel,
            signal_source, signal_data, status, expires_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           RETURNING action_id""",
        (
            str(a.action_id), str(a.person_id), a.priority, a.action_type,
            a.title, a.description, a.suggested_text, a.suggested_channel,
            a.signal_source, _to_json(a.signal_data), a.status, a.expires_at,
        ),
    ).fetchone()
    return row[0]


def get_pending_actions(
    conn: psycopg.Connection,
    person_id: UUID | None = None,
    limit: int = 50,
) -> list[dict]:
    conn.row_factory = dict_row
    if person_id:
        return conn.execute(
            """SELECT * FROM person_next_actions
               WHERE person_id = %s AND status = 'pending'
                 AND (snoozed_until IS NULL OR snoozed_until < now())
                 AND (expires_at IS NULL OR expires_at > now())
               ORDER BY priority ASC, generated_at DESC
               LIMIT %s""",
            (str(person_id), limit),
        ).fetchall()
    return conn.execute(
        """SELECT * FROM person_next_actions
           WHERE status = 'pending'
             AND (snoozed_until IS NULL OR snoozed_until < now())
             AND (expires_at IS NULL OR expires_at > now())
           ORDER BY priority ASC, generated_at DESC
           LIMIT %s""",
        (limit,),
    ).fetchall()


def update_action_status(
    conn: psycopg.Connection,
    action_id: UUID,
    status: str,
    snoozed_until: datetime | None = None,
) -> None:
    conn.execute(
        """UPDATE person_next_actions SET
               status = %s,
               done_at = CASE WHEN %s = 'done' THEN now() ELSE done_at END,
               snoozed_until = %s
           WHERE action_id = %s""",
        (status, status, snoozed_until, str(action_id)),
    )


def has_pending_action(
    conn: psycopg.Connection,
    person_id: UUID,
    action_type: str,
    within_days: int = 14,
) -> bool:
    row = conn.execute(
        """SELECT 1 FROM person_next_actions
           WHERE person_id = %s AND action_type = %s AND status = 'pending'
             AND generated_at > now() - make_interval(days => %s)
           LIMIT 1""",
        (str(person_id), action_type, within_days),
    ).fetchone()
    return row is not None


# ═══════════════════════════════════════════════════════════════════════
# Pipeline State (Warstwa 14)
# ═══════════════════════════════════════════════════════════════════════

def get_watermark(conn: psycopg.Connection, source_name: str) -> datetime | None:
    row = conn.execute(
        "SELECT last_run_at FROM pipeline_state WHERE source_name = %s",
        (source_name,),
    ).fetchone()
    if row and row[0]:
        return row[0]
    return None


def save_watermark(
    conn: psycopg.Connection,
    source_name: str,
    stats: dict,
    status: str = "success",
    error_message: str | None = None,
    run_duration_ms: int | None = None,
) -> None:
    conn.execute(
        """INSERT INTO pipeline_state
           (source_name, last_run_at, last_success_at, status,
            records_processed, records_new, records_updated,
            error_message, run_duration_ms)
           VALUES (%s, now(), CASE WHEN %s = 'success' THEN now() ELSE NULL END,
                   %s, %s, %s, %s, %s, %s)
           ON CONFLICT (source_name) DO UPDATE SET
               last_run_at = now(),
               last_success_at = CASE
                   WHEN %s = 'success' THEN now()
                   ELSE pipeline_state.last_success_at END,
               status = %s,
               records_processed = %s,
               records_new = %s,
               records_updated = %s,
               error_message = %s,
               run_duration_ms = %s""",
        (
            source_name, status,
            status, stats.get("processed", 0), stats.get("new", 0),
            stats.get("updated", 0), error_message, run_duration_ms,
            # ON CONFLICT params
            status, status,
            stats.get("processed", 0), stats.get("new", 0),
            stats.get("updated", 0), error_message, run_duration_ms,
        ),
    )


def acquire_pipeline_lock(conn: psycopg.Connection, source_name: str) -> bool:
    """Try to acquire a run lock. Returns False if already running."""
    cur = conn.execute(
        """UPDATE pipeline_state SET status = 'running', last_run_at = now()
           WHERE source_name = %s AND status != 'running'""",
        (source_name,),
    )
    if cur.rowcount == 0:
        # Maybe never_run — try insert
        try:
            conn.execute(
                """INSERT INTO pipeline_state (source_name, status, last_run_at)
                   VALUES (%s, 'running', now())""",
                (source_name,),
            )
            return True
        except psycopg.errors.UniqueViolation:
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════
# Full profile view
# ═══════════════════════════════════════════════════════════════════════

def get_full_profile(conn: psycopg.Connection, person_id: UUID) -> dict | None:
    conn.row_factory = dict_row
    return conn.execute(
        "SELECT * FROM v_person_full WHERE person_id = %s",
        (str(person_id),),
    ).fetchone()


def get_action_inbox(conn: psycopg.Connection, limit: int = 50) -> list[dict]:
    conn.row_factory = dict_row
    return conn.execute(
        "SELECT * FROM v_my_action_inbox LIMIT %s", (limit,)
    ).fetchall()


def get_relationship_spectrum(
    conn: psycopg.Connection, person_id_from: UUID
) -> list[dict]:
    conn.row_factory = dict_row
    return conn.execute(
        "SELECT * FROM v_relationship_spectrum WHERE person_id_from = %s",
        (str(person_id_from),),
    ).fetchall()
