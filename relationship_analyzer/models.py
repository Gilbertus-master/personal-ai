"""Pydantic models for relationship_analyzer."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PairData(BaseModel):
    """All data collected for one person pair, used as input to perspectives."""

    person_id_a: UUID
    person_id_b: UUID
    data_window_days: int = 365

    # person_relationships row (a->b direction)
    rel_a_to_b: dict[str, Any] | None = None
    # person_relationships row (b->a direction)
    rel_b_to_a: dict[str, Any] | None = None

    # person_behavioral for A and B
    behavioral_a: dict[str, Any] | None = None
    behavioral_b: dict[str, Any] | None = None

    # person_communication_pattern for A and B
    comm_a: dict[str, Any] | None = None
    comm_b: dict[str, Any] | None = None

    # person_psychographic for A and B
    psycho_a: dict[str, Any] | None = None
    psycho_b: dict[str, Any] | None = None

    # person_open_loops for A and B (lists)
    open_loops_a: list[dict[str, Any]] = Field(default_factory=list)
    open_loops_b: list[dict[str, Any]] = Field(default_factory=list)

    # person_shared_context for A and B (lists)
    shared_context_a: list[dict[str, Any]] = Field(default_factory=list)
    shared_context_b: list[dict[str, Any]] = Field(default_factory=list)

    # person_relationship_trajectory (a->b)
    trajectory_a_to_b: dict[str, Any] | None = None
    trajectory_b_to_a: dict[str, Any] | None = None

    # person_origin for A and B
    origin_a: dict[str, Any] | None = None
    origin_b: dict[str, Any] | None = None

    # person_professional for A and B
    professional_a: dict[str, Any] | None = None
    professional_b: dict[str, Any] | None = None

    # Display names
    name_a: str = ""
    name_b: str = ""

    # Shared contacts count (pre-computed)
    shared_contacts_count: int = 0


class PerspectiveResult(BaseModel):
    """Output of a single perspective computation."""

    perspective_name: str  # e.g. 'p1_behavioral'
    direction: str  # 'a_to_b', 'b_to_a', 'dyadic'
    fields: dict[str, Any] = Field(default_factory=dict)


class HealthScore(BaseModel):
    """Computed health score with label."""

    score: int = Field(ge=0, le=100)
    label: str  # 'excellent', 'good', 'fair', 'poor', 'at_risk'
    sub_scores: dict[str, float] = Field(default_factory=dict)


class AISynthesis(BaseModel):
    """AI-generated narrative synthesis."""

    narrative_summary: str = ""
    key_strengths: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    model_used: str = ""
    confidence: float = 0.0


class AnalysisResult(BaseModel):
    """Full output of a relationship analysis."""

    person_id_a: UUID
    person_id_b: UUID
    name_a: str = ""
    name_b: str = ""

    perspectives_a_to_b: dict[str, Any] = Field(default_factory=dict)
    perspectives_b_to_a: dict[str, Any] = Field(default_factory=dict)
    perspectives_dyadic: dict[str, Any] = Field(default_factory=dict)

    health: HealthScore | None = None
    ai_synthesis: AISynthesis | None = None

    data_window_days: int = 365
    interactions_analyzed: int = 0
    computed_at: datetime | None = None
