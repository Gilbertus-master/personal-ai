"""Core analyzer — orchestrates data collection, perspectives, scoring, AI, and persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import psycopg
import structlog

from .data_collector import collect_pair_data
from .perspectives import ALL_PERSPECTIVES
from .scorer import calculate_health_score
from .ai_synthesizer import generate_synthesis

log = structlog.get_logger("relationship_analyzer.analyzer")


def _average_perspectives(a_to_b: dict[str, Any], b_to_a: dict[str, Any]) -> dict[str, Any]:
    """Compute dyadic perspective by averaging both directions.

    For numeric fields: average. For strings: prefer a_to_b. For lists: merge.
    For booleans: OR. For timestamps: earlier.
    """
    all_keys = set(a_to_b.keys()) | set(b_to_a.keys())
    result: dict[str, Any] = {}

    for key in all_keys:
        val_a = a_to_b.get(key)
        val_b = b_to_a.get(key)

        if val_a is None and val_b is None:
            result[key] = None
            continue

        if val_a is None:
            result[key] = val_b
            continue

        if val_b is None:
            result[key] = val_a
            continue

        # Both non-None
        if isinstance(val_a, bool):
            result[key] = val_a or val_b
        elif isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
            result[key] = round((val_a + val_b) / 2.0, 3)
        elif isinstance(val_a, list) and isinstance(val_b, list):
            # Merge lists, deduplicate
            seen = set()
            merged = []
            for item in val_a + val_b:
                item_key = str(item).lower()
                if item_key not in seen:
                    seen.add(item_key)
                    merged.append(item)
            result[key] = merged
        elif isinstance(val_a, datetime) and isinstance(val_b, datetime):
            result[key] = min(val_a, val_b)
        else:
            # Strings, dicts, etc. — prefer a_to_b
            result[key] = val_a

    return result


def _upsert_analysis(
    conn: psycopg.Connection,
    person_id_a: UUID,
    person_id_b: UUID,
    perspective: str,
    fields: dict[str, Any],
    health_score: int | None,
    health_label: str | None,
    ai_data: dict[str, Any] | None,
    data_window_days: int,
    interactions_analyzed: int,
) -> None:
    """UPSERT a single analysis record into relationship_analyses."""
    # Build column list dynamically from fields present
    db_columns = {
        # P1
        "interaction_count_total": fields.get("interaction_count_total"),
        "interaction_count_30d": fields.get("interaction_count_30d"),
        "interaction_count_90d": fields.get("interaction_count_90d"),
        "avg_interactions_per_week": fields.get("avg_interactions_per_week"),
        "days_since_last_contact": fields.get("days_since_last_contact"),
        "longest_gap_days": fields.get("longest_gap_days"),
        "relationship_duration_days": fields.get("relationship_duration_days"),
        "active_channels_count": fields.get("active_channels_count"),
        "dominant_channel": fields.get("dominant_channel"),
        "avg_message_length_chars": fields.get("avg_message_length_chars"),
        "response_time_avg_minutes": fields.get("response_time_avg_minutes"),
        "response_time_p90_minutes": fields.get("response_time_p90_minutes"),
        # P2
        "initiation_ratio": fields.get("initiation_ratio"),
        "response_rate": fields.get("response_rate"),
        "avg_lag_ego_minutes": fields.get("avg_lag_ego_minutes"),
        "avg_lag_alter_minutes": fields.get("avg_lag_alter_minutes"),
        "lag_asymmetry": fields.get("lag_asymmetry"),
        "formality_score_ego": fields.get("formality_score_ego"),
        "formality_score_alter": fields.get("formality_score_alter"),
        "formality_asymmetry": fields.get("formality_asymmetry"),
        # P3
        "avg_sentiment_ego": fields.get("avg_sentiment_ego"),
        "avg_sentiment_alter": fields.get("avg_sentiment_alter"),
        "sentiment_variance_ego": fields.get("sentiment_variance_ego"),
        "sentiment_trend": fields.get("sentiment_trend"),
        "positive_signal_count": fields.get("positive_signal_count"),
        "negative_signal_count": fields.get("negative_signal_count"),
        "emotional_support_score": fields.get("emotional_support_score"),
        "conflict_detected": fields.get("conflict_detected"),
        "conflict_last_detected_at": fields.get("conflict_last_detected_at"),
        # P4
        "top_topics": fields.get("top_topics"),
        "topics_evolution": fields.get("topics_evolution"),
        "shared_entities_count": fields.get("shared_entities_count"),
        "discussion_depth_score": fields.get("discussion_depth_score"),
        # P5
        "trajectory_status": fields.get("trajectory_status"),
        "tie_strength_current": fields.get("tie_strength_current"),
        "tie_strength_delta_30d": fields.get("tie_strength_delta_30d"),
        "tie_strength_delta_90d": fields.get("tie_strength_delta_90d"),
        "peak_tie_strength": fields.get("peak_tie_strength"),
        "peak_tie_strength_at": fields.get("peak_tie_strength_at"),
        "lifecycle_stage": fields.get("lifecycle_stage"),
        "turning_points": fields.get("turning_points"),
        # P6
        "humor_signal_ratio": fields.get("humor_signal_ratio"),
        "question_ratio_ego": fields.get("question_ratio_ego"),
        "personal_question_ratio": fields.get("personal_question_ratio"),
        "language_accommodation": fields.get("language_accommodation"),
        "emotional_language_ratio": fields.get("emotional_language_ratio"),
        "support_language_ratio": fields.get("support_language_ratio"),
        "communication_style_match": fields.get("communication_style_match"),
        # P7
        "first_contact_at": fields.get("first_contact_at"),
        "origin_type": fields.get("origin_type"),
        "origin_context": fields.get("origin_context"),
        "shared_contacts_count": fields.get("shared_contacts_count"),
        "open_loops_count": fields.get("open_loops_count"),
        "shared_experiences_count": fields.get("shared_experiences_count"),
        "milestone_count": fields.get("milestone_count"),
        # Health
        "health_score": health_score,
        "health_label": health_label,
        # Metadata
        "data_window_days": data_window_days,
        "interactions_analyzed": interactions_analyzed,
        "is_stale": False,
    }

    # AI synthesis fields
    if ai_data:
        db_columns["narrative_summary"] = ai_data.get("narrative_summary")
        db_columns["key_strengths"] = ai_data.get("key_strengths")
        db_columns["key_risks"] = ai_data.get("key_risks")
        db_columns["opportunities"] = ai_data.get("opportunities")
        db_columns["recommended_action"] = ai_data.get("recommended_action")
        db_columns["ai_model_used"] = ai_data.get("model_used")
        db_columns["ai_confidence"] = ai_data.get("confidence")

    # Filter out None values for cleaner SQL, but keep explicit False/0
    insert_cols = {}
    for k, v in db_columns.items():
        if v is not None:
            insert_cols[k] = v
        elif k in ("conflict_detected", "is_stale"):
            insert_cols[k] = v if v is not None else False

    # Build UPSERT query
    col_names = ["person_id_a", "person_id_b", "perspective"] + list(insert_cols.keys())
    placeholders = ["%s"] * len(col_names)
    values = [str(person_id_a), str(person_id_b), perspective] + list(insert_cols.values())

    update_parts = [f"{col} = EXCLUDED.{col}" for col in insert_cols.keys()]
    update_parts.append("computed_at = now()")

    sql = (
        f"INSERT INTO relationship_analyses ({', '.join(col_names)}) "
        f"VALUES ({', '.join(placeholders)}) "
        f"ON CONFLICT (person_id_a, person_id_b, perspective) "
        f"DO UPDATE SET {', '.join(update_parts)}"
    )

    # Convert Python types for psycopg
    import json as json_mod
    processed_values = []
    for v in values:
        if isinstance(v, dict):
            processed_values.append(json_mod.dumps(v, ensure_ascii=False, default=str))
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            processed_values.append(json_mod.dumps(v, ensure_ascii=False, default=str))
        else:
            processed_values.append(v)

    with conn.cursor() as cur:
        cur.execute(sql, processed_values)


def _mark_briefings_stale(conn: psycopg.Connection, person_id_a: UUID, person_id_b: UUID) -> None:
    """Mark existing person briefings as stale after new analysis."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE person_briefings SET is_stale = true WHERE person_id IN (%s, %s) AND is_stale = false",
            (str(person_id_a), str(person_id_b)),
        )


def analyze_relationship(
    person_id_a: UUID,
    person_id_b: UUID,
    conn: psycopg.Connection,
    data_window_days: int = 365,
    generate_ai: bool = True,
) -> dict[str, Any]:
    """Analyze the relationship between two persons.

    Steps:
      1. Collect pair data from all person_profile tables
      2. Compute P1-P7 for a_to_b perspective
      3. Compute P1-P7 for b_to_a perspective
      4. Compute dyadic by averaging both
      5. Calculate health score from dyadic
      6. (Optional) Generate AI narrative
      7. UPSERT 3 records (a_to_b, b_to_a, dyadic)
      8. Mark briefings stale

    Returns:
        dict with analysis results.
    """
    log.info(
        "analyzing_relationship",
        person_a=str(person_id_a),
        person_b=str(person_id_b),
        window_days=data_window_days,
    )

    # Step 1: Collect data
    pair_data = collect_pair_data(person_id_a, person_id_b, conn, data_window_days)

    # Step 2-3: Compute perspectives for both directions
    perspectives_a_to_b: dict[str, Any] = {}
    perspectives_b_to_a: dict[str, Any] = {}

    for name, compute_fn in ALL_PERSPECTIVES:
        try:
            result_ab = compute_fn(pair_data, "a_to_b")
            perspectives_a_to_b.update(result_ab)
        except Exception:
            log.exception("perspective_failed", perspective=name, direction="a_to_b")

        try:
            result_ba = compute_fn(pair_data, "b_to_a")
            perspectives_b_to_a.update(result_ba)
        except Exception:
            log.exception("perspective_failed", perspective=name, direction="b_to_a")

    # Step 4: Dyadic
    perspectives_dyadic = _average_perspectives(perspectives_a_to_b, perspectives_b_to_a)

    # Step 5: Health score
    health_score, health_label = calculate_health_score(perspectives_dyadic)

    # Interactions analyzed
    interactions_analyzed = perspectives_dyadic.get("interaction_count_total", 0) or 0

    # Step 6: AI narrative
    ai_data = None
    if generate_ai:
        try:
            synthesis = generate_synthesis(
                pair_data.name_a,
                pair_data.name_b,
                perspectives_dyadic,
                health_score,
                health_label,
            )
            ai_data = synthesis.model_dump()
        except Exception:
            log.exception("ai_synthesis_skipped")

    # Step 7: UPSERT 3 records
    _upsert_analysis(
        conn, person_id_a, person_id_b, "a_to_b",
        perspectives_a_to_b, health_score, health_label, ai_data,
        data_window_days, interactions_analyzed,
    )
    _upsert_analysis(
        conn, person_id_a, person_id_b, "b_to_a",
        perspectives_b_to_a, health_score, health_label, ai_data,
        data_window_days, interactions_analyzed,
    )
    _upsert_analysis(
        conn, person_id_a, person_id_b, "dyadic",
        perspectives_dyadic, health_score, health_label, ai_data,
        data_window_days, interactions_analyzed,
    )

    # Step 8: Mark briefings stale
    _mark_briefings_stale(conn, person_id_a, person_id_b)

    conn.commit()

    result = {
        "person_id_a": str(person_id_a),
        "person_id_b": str(person_id_b),
        "name_a": pair_data.name_a,
        "name_b": pair_data.name_b,
        "health_score": health_score,
        "health_label": health_label,
        "lifecycle_stage": perspectives_dyadic.get("lifecycle_stage"),
        "trajectory_status": perspectives_dyadic.get("trajectory_status"),
        "tie_strength_current": perspectives_dyadic.get("tie_strength_current"),
        "interactions_analyzed": interactions_analyzed,
        "ai_narrative": ai_data.get("narrative_summary") if ai_data else None,
        "recommended_action": ai_data.get("recommended_action") if ai_data else None,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    log.info(
        "analysis_complete",
        name_a=pair_data.name_a,
        name_b=pair_data.name_b,
        health_score=health_score,
        health_label=health_label,
        lifecycle=perspectives_dyadic.get("lifecycle_stage"),
    )

    return result
