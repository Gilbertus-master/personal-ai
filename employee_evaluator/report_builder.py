"""Assemble evaluation data into a complete report with 9-box positioning."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import psycopg
import structlog

from .ai_synthesizer import synthesize_report
from .config import (
    DEFAULT_RETENTION_DAYS,
    NINE_BOX_HIGH_THRESHOLD,
    NINE_BOX_LOW_THRESHOLD,
)
from .models import CompetencyScore, NineBoxPosition

log = structlog.get_logger("employee_evaluator.report_builder")

# 9-box label matrix: [performance_level][potential_level]
NINE_BOX_LABELS = {
    ("high", "high"): "Star",
    ("high", "medium"): "High Performer",
    ("high", "low"): "Trusted Professional",
    ("medium", "high"): "High Potential",
    ("medium", "medium"): "Core Player",
    ("medium", "low"): "Consistent Contributor",
    ("low", "high"): "Rough Diamond",
    ("low", "medium"): "Inconsistent Talent",
    ("low", "low"): "Concern",
}


def build_report(
    person_id: UUID,
    cycle_id: UUID,
    scores: list[CompetencyScore],
    rel_data: dict[str, Any],
    evaluation_mode: str,
    report_type: str,
    conn: psycopg.Connection,
    display_name: str = "",
    overall_score: float | None = None,
    potential_score: float | None = None,
    data_completeness: float = 0.0,
    generate_ai: bool = True,
) -> dict[str, Any]:
    """Build a complete evaluation report.

    Steps:
    1. Compute 9-box position
    2. Generate AI narrative (if enabled)
    3. Persist report to DB
    4. Return report dict
    """
    # ── 9-box position ───────────────────────────────────────────────
    nine_box = _compute_nine_box(overall_score, potential_score)

    # ── AI narrative ─────────────────────────────────────────────────
    ai_report: dict[str, Any] | None = None
    if generate_ai:
        ai_report = synthesize_report(
            display_name=display_name,
            competency_scores=scores,
            relationship_data=rel_data,
            nine_box=nine_box,
            evaluation_mode=evaluation_mode,
            data_completeness=data_completeness,
        )

    # ── Assemble report ──────────────────────────────────────────────
    retention_until = date.today() + timedelta(days=DEFAULT_RETENTION_DAYS)

    report = {
        "person_id": str(person_id),
        "cycle_id": str(cycle_id),
        "report_type": report_type,
        "executive_summary": (ai_report or {}).get("executive_summary"),
        "narrative_strengths": (ai_report or {}).get("narrative_strengths"),
        "narrative_development": (ai_report or {}).get("narrative_development"),
        "key_strengths": (ai_report or {}).get("key_strengths", []),
        "development_areas": (ai_report or {}).get("development_areas", []),
        "suggested_actions": (ai_report or {}).get("suggested_actions", []),
        "nine_box_performance": nine_box.performance_level if nine_box else None,
        "nine_box_potential": nine_box.potential_level if nine_box else None,
        "nine_box_label": nine_box.label if nine_box else None,
        "gdpr_basis": "legitimate_interest",
        "retention_until": retention_until.isoformat(),
        "requires_human_review": True,
    }

    # ── Persist ──────────────────────────────────────────────────────
    _upsert_report(person_id, cycle_id, report_type, report, retention_until, conn)

    log.info(
        "report_built",
        person_id=str(person_id),
        cycle_id=str(cycle_id),
        report_type=report_type,
        nine_box=nine_box.label if nine_box else None,
        has_ai_narrative=ai_report is not None,
    )
    return report


def _compute_nine_box(
    overall_score: float | None,
    potential_score: float | None,
) -> NineBoxPosition | None:
    """Compute 9-box grid position from performance and potential scores."""
    if overall_score is None:
        return None

    perf_level = _to_level(overall_score)
    pot_level = _to_level(potential_score) if potential_score is not None else "medium"

    label = NINE_BOX_LABELS.get((perf_level, pot_level), "Unclassified")

    return NineBoxPosition(
        performance_level=perf_level,
        potential_level=pot_level,
        label=label,
    )


def _to_level(score: float) -> str:
    """Map score to high/medium/low level."""
    if score >= NINE_BOX_HIGH_THRESHOLD:
        return "high"
    elif score >= NINE_BOX_LOW_THRESHOLD:
        return "medium"
    else:
        return "low"


def _upsert_report(
    person_id: UUID,
    cycle_id: UUID,
    report_type: str,
    report: dict[str, Any],
    retention_until: date,
    conn: psycopg.Connection,
) -> None:
    """UPSERT report into employee_reports."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO employee_reports (
                   person_id, cycle_id, report_type,
                   executive_summary, narrative_strengths, narrative_development,
                   key_strengths, development_areas, suggested_actions,
                   nine_box_performance, nine_box_potential, nine_box_label,
                   gdpr_basis, retention_until, requires_human_review
               ) VALUES (
                   %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE
               )
               ON CONFLICT (person_id, cycle_id, report_type)
               DO UPDATE SET
                   executive_summary = EXCLUDED.executive_summary,
                   narrative_strengths = EXCLUDED.narrative_strengths,
                   narrative_development = EXCLUDED.narrative_development,
                   key_strengths = EXCLUDED.key_strengths,
                   development_areas = EXCLUDED.development_areas,
                   suggested_actions = EXCLUDED.suggested_actions,
                   nine_box_performance = EXCLUDED.nine_box_performance,
                   nine_box_potential = EXCLUDED.nine_box_potential,
                   nine_box_label = EXCLUDED.nine_box_label,
                   retention_until = EXCLUDED.retention_until,
                   requires_human_review = TRUE,
                   generated_at = NOW()""",
            (
                str(person_id),
                str(cycle_id),
                report_type,
                report.get("executive_summary"),
                report.get("narrative_strengths"),
                report.get("narrative_development"),
                json.dumps(report.get("key_strengths", []), ensure_ascii=False),
                json.dumps(report.get("development_areas", []), ensure_ascii=False),
                json.dumps(report.get("suggested_actions", []), ensure_ascii=False),
                report.get("nine_box_performance"),
                report.get("nine_box_potential"),
                report.get("nine_box_label"),
                "legitimate_interest",
                retention_until,
            ),
        )
