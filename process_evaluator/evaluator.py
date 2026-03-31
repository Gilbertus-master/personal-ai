"""Core evaluation orchestrator: evaluate a single business process."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from .ai_synthesizer import generate_process_narrative
from .dimensions import (
    compute_d1, compute_d2, compute_d3, compute_d4,
    compute_d5, compute_d6, compute_d7, compute_d8,
)
from .health_scorer import calculate_failure_risk, calculate_health_score, calculate_process_box
from .models import ProcessBox, ProcessEvaluationResult

log = structlog.get_logger("process_evaluator.evaluator")


def evaluate_process(
    process_id: UUID,
    cycle_id: UUID | None,
    conn: psycopg.Connection,
    generate_ai: bool = True,
) -> ProcessEvaluationResult:
    """Run full evaluation pipeline for a single process.

    Steps:
    1. Get process definition + latest process_metrics (8-12 weeks)
    2. Get process_participations for D8
    3. Compute D1-D8
    4. Calculate health_score, failure_risk, process_box
    5. Generate AI narrative (if enabled)
    6. UPSERT into process_competency_scores
    7. Return result with requires_human_review=True
    """
    result = ProcessEvaluationResult(
        process_id=process_id,
        cycle_id=cycle_id,
        process_name="",
    )

    # ── 1. Get process definition ───────────────────────────────────
    process_def = _get_process(process_id, conn)
    if not process_def:
        result.errors.append(f"Process {process_id} not found")
        return result

    result.process_name = process_def.get("process_name", "Unknown")
    process_type = process_def.get("process_type", "default")

    # ── 2. Get metrics (8-12 weeks) ─────────────────────────────────
    metrics_rows = _get_recent_metrics(process_id, conn, weeks=12)
    if metrics_rows:
        # Inject process_type into each row for D2
        for row in metrics_rows:
            row["process_type"] = process_type

        dates = [r.get("metric_date") for r in metrics_rows if r.get("metric_date")]
        if dates:
            result.data_period_start = min(dates)
            result.data_period_end = max(dates)
        result.events_analyzed = len(metrics_rows)

    # ── 3. Compute D1-D8 ───────────────────────────────────────────
    d1 = compute_d1(process_id, metrics_rows, process_def, conn)
    d2 = compute_d2(process_id, metrics_rows, conn)
    d3 = compute_d3(process_id, conn)
    d4 = compute_d4(process_id, metrics_rows, conn)
    d5 = compute_d5(process_id, metrics_rows, process_def, conn)
    d6 = compute_d6(process_id, metrics_rows, conn)
    d7 = compute_d7(process_id, metrics_rows, conn)
    d8 = compute_d8(process_id, conn)

    all_scores = [d1, d2, d3, d4, d5, d6, d7, d8]
    result.dimension_scores = all_scores
    scores_dict = {s.name: s for s in all_scores}

    # Data completeness: fraction of dimensions that have scores
    scored_count = sum(1 for s in all_scores if s.score is not None)
    result.data_completeness = round(scored_count / 8.0, 2)

    # ── 4. Calculate health_score, failure_risk, process_box ────────
    health_score, health_label = calculate_health_score(all_scores, process_type)
    result.overall_health_score = health_score
    result.health_label = health_label

    failure_risk = calculate_failure_risk(scores_dict)
    result.failure_risk_score = failure_risk

    # Maturity level for box calculation
    pml = None
    if d3.evidence.get("pml_level"):
        pml = d3.evidence["pml_level"]
    elif d3.evidence.get("estimated_pml"):
        pml = d3.evidence["estimated_pml"]
    result.process_maturity_level = pml

    box_health, box_maturity, box_label = calculate_process_box(health_score, pml)
    result.process_box = ProcessBox(
        health_level=box_health,
        maturity_level=box_maturity,
        label=box_label,
    )

    # Extract D8 details
    if d8.evidence:
        result.bus_factor = d8.evidence.get("bus_factor")
        result.knowledge_concentration = d8.evidence.get("knowledge_concentration")
        result.flight_risk_weighted = d8.evidence.get("flight_risk_weighted")
        result.upstream_risk_score = d8.evidence.get("upstream_risk")
        crit_ids = d8.evidence.get("critical_person_ids", [])
        result.critical_person_ids = [UUID(pid) for pid in crit_ids if pid]

    # Extract D5 cost details
    if d5.evidence:
        result.cost_per_unit_pln = d5.evidence.get("avg_cost_per_unit")
        result.cost_vs_benchmark = d5.evidence.get("cost_vs_benchmark")

    # Extract D7 scalability details
    if d7.evidence:
        result.capacity_headroom_pct = d7.evidence.get("capacity_headroom_pct")
        result.estimated_breaking_point_x = d7.evidence.get("breaking_point_x")

    # ── 5. Generate AI narrative ────────────────────────────────────
    if generate_ai:
        ai_result = generate_process_narrative(
            process_name=result.process_name,
            process_type=process_type,
            scores_dict=scores_dict,
            health_score=health_score,
            failure_risk=failure_risk,
            box_label=box_label,
            conn=conn,
        )
        if ai_result:
            result.ai_narrative = ai_result.get("narrative")
            result.ai_key_findings = ai_result.get("key_findings", [])
            result.ai_recommendations = ai_result.get("recommendations", [])
            result.ai_model_used = ai_result.get("model_used")

    # ── 6. UPSERT into process_competency_scores ───────────────────
    _upsert_scores(result, conn)

    # ── 7. Return ───────────────────────────────────────────────────
    result.requires_human_review = True

    log.info(
        "process_evaluation_complete",
        process_id=str(process_id),
        process_name=result.process_name,
        health_score=health_score,
        health_label=health_label,
        failure_risk=failure_risk,
        box_label=box_label,
        completeness=result.data_completeness,
    )

    return result


# ── Private helpers ──────────────────────────────────────────────────

def _get_process(process_id: UUID, conn: psycopg.Connection) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT process_id, process_name, process_type, status,
                      sla_target_hours, cost_per_unit_pln, parent_process_id
               FROM processes WHERE process_id = %s""",
            (str(process_id),),
        )
        return cur.fetchone()


def _get_recent_metrics(
    process_id: UUID,
    conn: psycopg.Connection,
    weeks: int = 12,
) -> list[dict[str, Any]]:
    """Get last N weeks of process_metrics, ordered oldest-first."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT *
               FROM process_metrics
               WHERE process_id = %s
                 AND metric_date >= CURRENT_DATE - (%s * INTERVAL '7 days')
               ORDER BY metric_date ASC""",
            (str(process_id), weeks),
        )
        return cur.fetchall()


def _upsert_scores(result: ProcessEvaluationResult, conn: psycopg.Connection) -> None:
    """UPSERT all dimension scores into process_competency_scores."""
    score_map = {s.name: s for s in result.dimension_scores}

    def _s(name: str) -> float | None:
        ds = score_map.get(name)
        return ds.score if ds else None

    def _c(name: str) -> float:
        ds = score_map.get(name)
        return ds.confidence if ds else 0.0

    def _e(name: str) -> str | None:
        ds = score_map.get(name)
        if ds and ds.evidence:
            return json.dumps(ds.evidence, default=str, ensure_ascii=False)
        return None

    critical_ids = (
        [str(pid) for pid in result.critical_person_ids]
        if result.critical_person_ids else None
    )

    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO process_competency_scores (
                   process_id, cycle_id,
                   score_throughput, throughput_evidence, throughput_confidence,
                   score_quality, quality_evidence, quality_confidence,
                   score_maturity, maturity_evidence, maturity_confidence,
                   process_maturity_level, maturity_survey_date,
                   score_handoff, handoff_evidence, handoff_confidence,
                   score_cost, cost_evidence, cost_confidence,
                   cost_per_unit_pln, cost_vs_benchmark,
                   score_improvement, improvement_evidence, improvement_confidence,
                   score_scalability, scalability_evidence, scalability_confidence,
                   capacity_headroom_pct, estimated_breaking_point_x,
                   score_dependency, dependency_evidence, dependency_confidence,
                   bus_factor, knowledge_concentration, flight_risk_weighted,
                   upstream_risk_score, critical_person_ids,
                   overall_health_score, health_label, failure_risk_score,
                   process_box_health, process_box_maturity, process_box_label,
                   data_period_start, data_period_end, events_analyzed, data_completeness,
                   requires_human_review,
                   ai_narrative, ai_key_findings, ai_recommendations, ai_model_used
               ) VALUES (
                   %s, %s,
                   %s, %s, %s,
                   %s, %s, %s,
                   %s, %s, %s,
                   %s, NULL,
                   %s, %s, %s,
                   %s, %s, %s,
                   %s, %s,
                   %s, %s, %s,
                   %s, %s, %s,
                   %s, %s,
                   %s, %s, %s,
                   %s, %s, %s,
                   %s, %s,
                   %s, %s, %s,
                   %s, %s, %s,
                   %s, %s, %s, %s,
                   TRUE,
                   %s, %s, %s, %s
               )
               ON CONFLICT (process_id, cycle_id)
               DO UPDATE SET
                   score_throughput = EXCLUDED.score_throughput,
                   throughput_evidence = EXCLUDED.throughput_evidence,
                   throughput_confidence = EXCLUDED.throughput_confidence,
                   score_quality = EXCLUDED.score_quality,
                   quality_evidence = EXCLUDED.quality_evidence,
                   quality_confidence = EXCLUDED.quality_confidence,
                   score_maturity = EXCLUDED.score_maturity,
                   maturity_evidence = EXCLUDED.maturity_evidence,
                   maturity_confidence = EXCLUDED.maturity_confidence,
                   process_maturity_level = EXCLUDED.process_maturity_level,
                   score_handoff = EXCLUDED.score_handoff,
                   handoff_evidence = EXCLUDED.handoff_evidence,
                   handoff_confidence = EXCLUDED.handoff_confidence,
                   score_cost = EXCLUDED.score_cost,
                   cost_evidence = EXCLUDED.cost_evidence,
                   cost_confidence = EXCLUDED.cost_confidence,
                   cost_per_unit_pln = EXCLUDED.cost_per_unit_pln,
                   cost_vs_benchmark = EXCLUDED.cost_vs_benchmark,
                   score_improvement = EXCLUDED.score_improvement,
                   improvement_evidence = EXCLUDED.improvement_evidence,
                   improvement_confidence = EXCLUDED.improvement_confidence,
                   score_scalability = EXCLUDED.score_scalability,
                   scalability_evidence = EXCLUDED.scalability_evidence,
                   scalability_confidence = EXCLUDED.scalability_confidence,
                   capacity_headroom_pct = EXCLUDED.capacity_headroom_pct,
                   estimated_breaking_point_x = EXCLUDED.estimated_breaking_point_x,
                   score_dependency = EXCLUDED.score_dependency,
                   dependency_evidence = EXCLUDED.dependency_evidence,
                   dependency_confidence = EXCLUDED.dependency_confidence,
                   bus_factor = EXCLUDED.bus_factor,
                   knowledge_concentration = EXCLUDED.knowledge_concentration,
                   flight_risk_weighted = EXCLUDED.flight_risk_weighted,
                   upstream_risk_score = EXCLUDED.upstream_risk_score,
                   critical_person_ids = EXCLUDED.critical_person_ids,
                   overall_health_score = EXCLUDED.overall_health_score,
                   health_label = EXCLUDED.health_label,
                   failure_risk_score = EXCLUDED.failure_risk_score,
                   process_box_health = EXCLUDED.process_box_health,
                   process_box_maturity = EXCLUDED.process_box_maturity,
                   process_box_label = EXCLUDED.process_box_label,
                   data_period_start = EXCLUDED.data_period_start,
                   data_period_end = EXCLUDED.data_period_end,
                   events_analyzed = EXCLUDED.events_analyzed,
                   data_completeness = EXCLUDED.data_completeness,
                   requires_human_review = TRUE,
                   ai_narrative = EXCLUDED.ai_narrative,
                   ai_key_findings = EXCLUDED.ai_key_findings,
                   ai_recommendations = EXCLUDED.ai_recommendations,
                   ai_model_used = EXCLUDED.ai_model_used,
                   computed_at = NOW()""",
            (
                str(result.process_id),
                str(result.cycle_id) if result.cycle_id else None,
                # D1
                _s("throughput"), _e("throughput"), _c("throughput"),
                # D2
                _s("quality"), _e("quality"), _c("quality"),
                # D3
                _s("maturity"), _e("maturity"), _c("maturity"),
                result.process_maturity_level,
                # D4
                _s("handoff"), _e("handoff"), _c("handoff"),
                # D5
                _s("cost"), _e("cost"), _c("cost"),
                result.cost_per_unit_pln, result.cost_vs_benchmark,
                # D6
                _s("improvement"), _e("improvement"), _c("improvement"),
                # D7
                _s("scalability"), _e("scalability"), _c("scalability"),
                result.capacity_headroom_pct, result.estimated_breaking_point_x,
                # D8
                _s("dependency"), _e("dependency"), _c("dependency"),
                result.bus_factor, result.knowledge_concentration,
                result.flight_risk_weighted, result.upstream_risk_score,
                critical_ids,
                # Composite
                result.overall_health_score, result.health_label, result.failure_risk_score,
                # Box
                result.process_box.health_level if result.process_box else None,
                result.process_box.maturity_level if result.process_box else None,
                result.process_box.label if result.process_box else None,
                # Data
                result.data_period_start, result.data_period_end,
                result.events_analyzed, result.data_completeness,
                # AI
                result.ai_narrative,
                result.ai_key_findings or None,
                result.ai_recommendations or None,
                result.ai_model_used,
            ),
        )
