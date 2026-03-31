"""Pydantic-style dataclass models for process evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID


@dataclass
class DimensionScore:
    """Score for a single process dimension (D1-D8)."""

    name: str
    score: float | None = None        # 1.0-5.0, None if no data
    confidence: float = 0.0           # 0.0-1.0
    evidence: dict[str, Any] = field(default_factory=dict)
    sub_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ProcessEvaluationInput:
    """All input data needed for a process evaluation."""

    process_id: UUID
    process_name: str
    process_type: str = "default"
    metrics_rows: list[dict[str, Any]] = field(default_factory=list)
    process_def: dict[str, Any] = field(default_factory=dict)
    participations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ProcessBox:
    """Process box position (Health x Maturity) — analogous to 9-box."""

    health_level: str       # 'high', 'medium', 'low'
    maturity_level: str     # 'high', 'medium', 'low'
    label: str              # 'Institutionalized', 'Hero-Dependent', etc.


@dataclass
class ProcessEvaluationResult:
    """Complete process evaluation output."""

    process_id: UUID
    cycle_id: UUID | None
    process_name: str
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    overall_health_score: float | None = None
    health_label: str | None = None
    failure_risk_score: float | None = None
    process_box: ProcessBox | None = None
    process_maturity_level: int | None = None
    bus_factor: int | None = None
    knowledge_concentration: float | None = None
    flight_risk_weighted: float | None = None
    upstream_risk_score: float | None = None
    critical_person_ids: list[UUID] = field(default_factory=list)
    cost_per_unit_pln: float | None = None
    cost_vs_benchmark: float | None = None
    capacity_headroom_pct: float | None = None
    estimated_breaking_point_x: float | None = None
    data_period_start: date | None = None
    data_period_end: date | None = None
    events_analyzed: int = 0
    data_completeness: float = 0.0
    ai_narrative: str | None = None
    ai_key_findings: list[str] = field(default_factory=list)
    ai_recommendations: list[str] = field(default_factory=list)
    ai_model_used: str | None = None
    requires_human_review: bool = True
    errors: list[str] = field(default_factory=list)
