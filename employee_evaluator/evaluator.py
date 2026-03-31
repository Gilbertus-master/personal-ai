"""Core evaluation orchestrator: evaluate a single employee."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from .collectors.profile_collector import collect_profile_data
from .collectors.signal_aggregator import aggregate_signals
from .competency.framework import calculate_overall_score, get_competency_weights
from .competency.scorer import score_all_competencies
from .compliance.audit_logger import log_action
from .models import CompetencyScore, EvaluationResult
from .relationship_enricher import enrich_with_relationships
from .report_builder import build_report

log = structlog.get_logger("employee_evaluator.evaluator")


def evaluate_employee(
    person_id: UUID,
    cycle_id: UUID,
    conn: psycopg.Connection,
    generate_ai: bool = True,
    report_types: list[str] | None = None,
) -> EvaluationResult:
    """Run full evaluation pipeline for a single employee.

    Steps:
    1. Compliance check (employees_notified_at)
    2. Get person, role_config, cycle
    3. Collect signals from profile_collector
    4. Aggregate signals
    5. Score 8 competencies
    6. Enrich with relationships
    7. Calculate overall + 9-box
    8. Generate AI report (if enabled)
    9. UPSERT competency_scores + reports
    10. Audit log
    11. Return result with requires_human_review=True

    Args:
        person_id: UUID of the person to evaluate.
        cycle_id: UUID of the evaluation cycle.
        conn: Database connection (from pool).
        generate_ai: Whether to generate AI narrative report.
        report_types: List of report types to generate (default: ['manager_only']).

    Returns:
        EvaluationResult with all scores, reports, and metadata.
    """
    if report_types is None:
        report_types = ["manager_only"]

    result = EvaluationResult(
        person_id=person_id,
        cycle_id=cycle_id,
        display_name="",
    )

    # ── 1. Compliance check ──────────────────────────────────────────
    org_config = _get_org_config(conn)
    if not org_config or not org_config.get("employees_notified_at"):
        error = "Compliance violation: employees_notified_at is NULL. Cannot proceed with evaluation."
        log.error("compliance_check_failed", person_id=str(person_id), error=error)
        result.errors.append(error)
        log_action("evaluation_blocked_compliance", person_id, {"reason": error}, "system", conn)
        return result

    log_action("evaluation_started", person_id, {"cycle_id": str(cycle_id)}, "system", conn)

    # ── 2. Get person, role_config, cycle ────────────────────────────
    person = _get_person(person_id, conn)
    if not person:
        result.errors.append(f"Person {person_id} not found")
        return result

    result.display_name = person["display_name"]

    role_config = _get_role_config(person_id, conn)
    seniority_level = role_config.get("seniority_level", "mid") if role_config else "mid"

    cycle = _get_cycle(cycle_id, conn)
    if not cycle:
        result.errors.append(f"Cycle {cycle_id} not found")
        return result

    evaluation_mode = cycle.get("evaluation_mode", org_config.get("evaluation_mode", "development"))

    # ── 3. Collect profile data ──────────────────────────────────────
    log_action("data_accessed", person_id, {"source": "profile_collector"}, "system", conn)
    profile_data = collect_profile_data(person_id, conn)

    # ── 4. Aggregate signals ─────────────────────────────────────────
    log_action("data_accessed", person_id, {"source": "employee_signals"}, "system", conn)
    signals = aggregate_signals(
        person_id,
        cycle["period_start"],
        cycle["period_end"],
        conn,
    )

    # ── 5. Score 8 competencies ──────────────────────────────────────
    previous_scores = _get_previous_scores(person_id, cycle_id, conn)

    # ── 6. Enrich with relationships ─────────────────────────────────
    log_action("data_accessed", person_id, {"source": "relationship_analyses"}, "system", conn)
    rel_data = enrich_with_relationships(person_id, conn)

    # ── Score ────────────────────────────────────────────────────────
    competency_scores = score_all_competencies(
        signals=signals,
        profile_data=profile_data,
        relationship_data=rel_data,
        seniority_level=seniority_level,
        previous_scores=previous_scores,
    )
    result.competency_scores = competency_scores

    # ── 7. Calculate overall + potential ─────────────────────────────
    weights = get_competency_weights(role_config)
    overall_score, overall_label = calculate_overall_score(competency_scores, weights)
    result.overall_score = overall_score
    result.overall_label = overall_label
    result.data_completeness = signals.data_completeness

    # Potential = weighted average of growth, initiative, leadership
    potential_scores = [s for s in competency_scores if s.name in ("growth", "initiative", "leadership") and s.score is not None]
    if potential_scores:
        result.potential_score = round(
            sum(s.score * s.confidence for s in potential_scores)
            / sum(s.confidence for s in potential_scores if s.confidence > 0)
            if sum(s.confidence for s in potential_scores) > 0
            else 0.0,
            2,
        )

    # Flight risk: high if declining relationships + low growth
    result.flight_risk_score = _estimate_flight_risk(competency_scores, rel_data)

    # ── 9. UPSERT competency_scores ──────────────────────────────────
    _upsert_competency_scores(person_id, cycle_id, competency_scores, result, conn)

    # ── 8. Generate AI reports ───────────────────────────────────────
    for rtype in report_types:
        report = build_report(
            person_id=person_id,
            cycle_id=cycle_id,
            scores=competency_scores,
            rel_data=rel_data,
            evaluation_mode=evaluation_mode,
            report_type=rtype,
            conn=conn,
            display_name=result.display_name,
            overall_score=overall_score,
            potential_score=result.potential_score,
            data_completeness=signals.data_completeness,
            generate_ai=generate_ai,
        )
        result.report = report

    # ── 10. Audit log ────────────────────────────────────────────────
    log_action(
        "evaluation_completed",
        person_id,
        {
            "cycle_id": str(cycle_id),
            "overall_score": overall_score,
            "overall_label": overall_label,
            "data_completeness": signals.data_completeness,
            "competencies_scored": sum(1 for s in competency_scores if s.score is not None),
        },
        "system",
        conn,
    )

    # ── 11. Return ───────────────────────────────────────────────────
    result.requires_human_review = True

    log.info(
        "evaluation_complete",
        person_id=str(person_id),
        display_name=result.display_name,
        overall_score=overall_score,
        overall_label=overall_label,
        completeness=round(signals.data_completeness, 2),
    )
    return result


# ── Private helpers ──────────────────────────────────────────────────

def _get_org_config(conn: psycopg.Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT evaluation_mode, content_analysis_enabled,
                      legal_basis, employees_notified_at, default_retention_days
               FROM org_configs WHERE org_key = 'default'"""
        )
        return cur.fetchone()


def _get_person(person_id: UUID, conn: psycopg.Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT person_id, display_name, tags FROM persons WHERE person_id = %s""",
            (str(person_id),),
        )
        return cur.fetchone()


def _get_role_config(person_id: UUID, conn: psycopg.Connection) -> dict[str, Any] | None:
    """Get role config by matching person's job title to role_configs."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT rc.*
               FROM role_configs rc
               JOIN person_professional pp ON LOWER(pp.job_title) = LOWER(rc.role_name)
               WHERE pp.person_id = %s
               ORDER BY pp.updated_at DESC NULLS LAST
               LIMIT 1""",
            (str(person_id),),
        )
        return cur.fetchone()


def _get_cycle(cycle_id: UUID, conn: psycopg.Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT cycle_id, cycle_name, cycle_type, evaluation_mode,
                      period_start, period_end, status
               FROM evaluation_cycles WHERE cycle_id = %s""",
            (str(cycle_id),),
        )
        return cur.fetchone()


def _get_previous_scores(
    person_id: UUID,
    current_cycle_id: UUID,
    conn: psycopg.Connection,
) -> dict[str, float] | None:
    """Get scores from the most recent previous cycle."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT delivery_score, collaboration_score, communication_score,
                      initiative_score, knowledge_score, leadership_score,
                      growth_score, relationships_score
               FROM employee_competency_scores
               WHERE person_id = %s AND cycle_id != %s
               ORDER BY scored_at DESC
               LIMIT 1""",
            (str(person_id), str(current_cycle_id)),
        )
        row = cur.fetchone()

    if not row:
        return None

    scores = {}
    for name in ("delivery", "collaboration", "communication", "initiative",
                 "knowledge", "leadership", "growth", "relationships"):
        val = row.get(f"{name}_score")
        if val is not None:
            scores[name] = val
    return scores if scores else None


def _estimate_flight_risk(
    scores: list[CompetencyScore],
    rel_data: dict[str, Any],
) -> float | None:
    """Estimate flight risk on 0-1 scale. Higher = more at risk."""
    risk_signals = 0.0
    signal_count = 0

    # Declining relationships
    cooling = rel_data.get("cooling_count", 0)
    growing = rel_data.get("growing_count", 0)
    if cooling + growing > 0:
        cooling_ratio = cooling / (cooling + growing)
        risk_signals += cooling_ratio
        signal_count += 1

    # Low growth score
    for s in scores:
        if s.name == "growth" and s.score is not None:
            # Score < 2.5 = risk signal
            if s.score < 2.5:
                risk_signals += (2.5 - s.score) / 2.5
            signal_count += 1

    # Low relationship score
    for s in scores:
        if s.name == "relationships" and s.score is not None:
            if s.score < 2.5:
                risk_signals += (2.5 - s.score) / 2.5
            signal_count += 1

    if signal_count == 0:
        return None

    return round(min(1.0, risk_signals / signal_count), 2)


def _upsert_competency_scores(
    person_id: UUID,
    cycle_id: UUID,
    scores: list[CompetencyScore],
    result: EvaluationResult,
    conn: psycopg.Connection,
) -> None:
    """UPSERT all competency scores into employee_competency_scores."""
    score_map = {s.name: s for s in scores}

    def _s(name: str) -> float | None:
        cs = score_map.get(name)
        return cs.score if cs else None

    def _c(name: str) -> float:
        cs = score_map.get(name)
        return cs.confidence if cs else 0.0

    def _e(name: str) -> str | None:
        cs = score_map.get(name)
        if cs and cs.evidence:
            return json.dumps(cs.evidence, default=str, ensure_ascii=False)
        return None

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO employee_competency_scores (
                   person_id, cycle_id,
                   delivery_score, delivery_evidence, delivery_confidence,
                   collaboration_score, collaboration_evidence, collaboration_confidence,
                   communication_score, communication_evidence, communication_confidence,
                   initiative_score, initiative_evidence, initiative_confidence,
                   knowledge_score, knowledge_evidence, knowledge_confidence,
                   leadership_score, leadership_evidence, leadership_confidence,
                   growth_score, growth_evidence, growth_confidence,
                   relationships_score, relationships_evidence, relationships_confidence,
                   overall_score, overall_label, potential_score,
                   flight_risk_score, data_completeness, requires_human_review
               ) VALUES (
                   %s, %s,
                   %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   %s, %s, %s, %s, %s, TRUE
               )
               ON CONFLICT (person_id, cycle_id)
               DO UPDATE SET
                   delivery_score = EXCLUDED.delivery_score,
                   delivery_evidence = EXCLUDED.delivery_evidence,
                   delivery_confidence = EXCLUDED.delivery_confidence,
                   collaboration_score = EXCLUDED.collaboration_score,
                   collaboration_evidence = EXCLUDED.collaboration_evidence,
                   collaboration_confidence = EXCLUDED.collaboration_confidence,
                   communication_score = EXCLUDED.communication_score,
                   communication_evidence = EXCLUDED.communication_evidence,
                   communication_confidence = EXCLUDED.communication_confidence,
                   initiative_score = EXCLUDED.initiative_score,
                   initiative_evidence = EXCLUDED.initiative_evidence,
                   initiative_confidence = EXCLUDED.initiative_confidence,
                   knowledge_score = EXCLUDED.knowledge_score,
                   knowledge_evidence = EXCLUDED.knowledge_evidence,
                   knowledge_confidence = EXCLUDED.knowledge_confidence,
                   leadership_score = EXCLUDED.leadership_score,
                   leadership_evidence = EXCLUDED.leadership_evidence,
                   leadership_confidence = EXCLUDED.leadership_confidence,
                   growth_score = EXCLUDED.growth_score,
                   growth_evidence = EXCLUDED.growth_evidence,
                   growth_confidence = EXCLUDED.growth_confidence,
                   relationships_score = EXCLUDED.relationships_score,
                   relationships_evidence = EXCLUDED.relationships_evidence,
                   relationships_confidence = EXCLUDED.relationships_confidence,
                   overall_score = EXCLUDED.overall_score,
                   overall_label = EXCLUDED.overall_label,
                   potential_score = EXCLUDED.potential_score,
                   flight_risk_score = EXCLUDED.flight_risk_score,
                   data_completeness = EXCLUDED.data_completeness,
                   requires_human_review = TRUE,
                   scored_at = NOW()""",
            (
                str(person_id), str(cycle_id),
                _s("delivery"), _e("delivery"), _c("delivery"),
                _s("collaboration"), _e("collaboration"), _c("collaboration"),
                _s("communication"), _e("communication"), _c("communication"),
                _s("initiative"), _e("initiative"), _c("initiative"),
                _s("knowledge"), _e("knowledge"), _c("knowledge"),
                _s("leadership"), _e("leadership"), _c("leadership"),
                _s("growth"), _e("growth"), _c("growth"),
                _s("relationships"), _e("relationships"), _c("relationships"),
                result.overall_score, result.overall_label, result.potential_score,
                result.flight_risk_score, result.data_completeness,
            ),
        )
