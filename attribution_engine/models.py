"""Pydantic models for the Attribution Engine."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AnomalySignal(BaseModel):
    """A single detected anomaly in a process metric."""
    metric_name: str
    current_value: float
    baseline_value: float
    sigma_deviation: float
    direction: str = Field(description="'problem' or 'success'")
    anomaly_type: str = Field(default="deviation", description="'deviation', 'sustained_decline', 'sudden_drop'")
    weeks_declining: int = 0


class PersonContribution(BaseModel):
    """A person's contribution signal for a specific process."""
    person_id: UUID
    person_name: str
    contribution_score: float = Field(ge=-1.0, le=1.0)
    tasks_overdue_ratio: float = 0.0
    flight_risk: float = 0.0
    delivery_score: float = 0.0
    escalations_ratio: float = 0.0
    role: Optional[str] = None


class TeamAnalysis(BaseModel):
    """Aggregated team-level analysis."""
    team_id: str
    team_name: Optional[str] = None
    week_start: date
    team_health: float = 0.0
    process_count: int = 0
    top_problems: list[dict] = Field(default_factory=list)
    top_performers: list[PersonContribution] = Field(default_factory=list)
    worst_performers: list[PersonContribution] = Field(default_factory=list)


class AttributionResult(BaseModel):
    """Full attribution result for a process-week pair."""
    attribution_id: Optional[UUID] = None
    process_id: UUID
    week_start: date

    direction: str = "neutral"
    severity: Optional[str] = None

    attribution_process: float = 0.0
    attribution_people: float = 0.0
    attribution_interaction: float = 0.0
    attribution_external: float = 0.0
    attribution_unknown: float = 0.0

    confidence: float = 0.0
    data_points_count: int = 0
    min_weeks_data: int = 0

    process_signals: dict = Field(default_factory=dict)
    people_signals: dict = Field(default_factory=dict)
    interaction_signals: dict = Field(default_factory=dict)

    team_id: Optional[str] = None
    team_health_contribution: Optional[float] = None

    top_people_positive: list[dict] = Field(default_factory=list)
    top_people_negative: list[dict] = Field(default_factory=list)

    primary_recommendation: Optional[str] = None
    recommendation_type: Optional[str] = None
    narrative: Optional[str] = None
    ai_confidence: Optional[float] = None

    computed_at: Optional[datetime] = None


class OrgHealthSnapshot(BaseModel):
    """Organization-wide health snapshot for a given week."""
    snapshot_id: Optional[UUID] = None
    week_start: date

    org_health_score: int = 0
    org_health_label: str = "unknown"
    score_delta_1w: Optional[float] = None
    score_delta_4w: Optional[float] = None

    # Q1: Money
    financial_waste_pln: Optional[float] = None
    top_cost_processes: list[dict] = Field(default_factory=list)
    budget_overruns_count: int = 0

    # Q2: People
    critical_people_at_risk: int = 0
    high_impact_departures: list[dict] = Field(default_factory=list)
    team_instability_score: float = 0.0

    # Q3: Process
    process_health_avg: float = 0.0
    critical_processes: int = 0
    processes_improving: int = 0
    processes_declining: int = 0

    # Q4: Investment
    top_investment_opps: list[dict] = Field(default_factory=list)

    dept_health_breakdown: dict = Field(default_factory=dict)
    critical_alerts: list[dict] = Field(default_factory=list)
    warning_alerts: list[dict] = Field(default_factory=list)

    computed_at: Optional[datetime] = None
