"""Pydantic models for process_collector."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProcessDefinition(BaseModel):
    """A business process definition."""

    process_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    process_name: str
    process_type: str  # engineering | sales | customer_service | finance | operations
    process_category: Optional[str] = None
    parent_process_id: Optional[uuid.UUID] = None
    team_id: Optional[str] = None
    sla_target_hours: Optional[float] = None
    cost_per_unit_pln: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessMetric(BaseModel):
    """Weekly aggregate metrics for a process."""

    metric_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    process_id: uuid.UUID
    week_start: date

    # Flow
    throughput: Optional[int] = None
    avg_cycle_time_h: Optional[float] = None
    p90_cycle_time_h: Optional[float] = None
    overdue_count: Optional[int] = None
    overdue_rate: Optional[float] = None
    error_rate: Optional[float] = None
    rework_rate: Optional[float] = None

    # Jira
    velocity_points: Optional[int] = None
    velocity_vs_plan: Optional[float] = None
    bugs_introduced: Optional[int] = None
    blockers_count: Optional[int] = None
    wip_count: Optional[int] = None
    lead_time_days: Optional[float] = None
    flow_efficiency: Optional[float] = None

    # Sales
    revenue_pln: Optional[float] = None
    deals_closed: Optional[int] = None
    deals_lost: Optional[int] = None
    conversion_rate: Optional[float] = None
    avg_deal_size_pln: Optional[float] = None
    avg_sales_cycle_days: Optional[float] = None
    pipeline_value_pln: Optional[float] = None
    quota_attainment: Optional[float] = None

    # Customer service
    tickets_resolved: Optional[int] = None
    avg_first_response_h: Optional[float] = None
    avg_resolution_h: Optional[float] = None
    escalation_rate: Optional[float] = None
    csat_score: Optional[float] = None
    nps_score: Optional[float] = None
    first_contact_resolution_rate: Optional[float] = None

    # Engineering
    deployments_count: Optional[int] = None
    deployment_failures: Optional[int] = None
    change_failure_rate: Optional[float] = None
    mttr_hours: Optional[float] = None
    code_coverage_pct: Optional[float] = None
    critical_bugs_open: Optional[int] = None
    tech_debt_hours: Optional[int] = None

    # Finance
    cost_actual_pln: Optional[float] = None
    cost_budget_pln: Optional[float] = None
    budget_variance_pct: Optional[float] = None
    margin_pct: Optional[float] = None
    cost_per_unit: Optional[float] = None

    # Health
    process_health_score: Optional[float] = None
    health_trend: Optional[float] = None
    anomaly_flags: list[str] = Field(default_factory=list)

    # Meta
    sources_collected: list[str] = Field(default_factory=list)
    collection_errors: Optional[dict] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class ProcessParticipation(BaseModel):
    """Who participated in which process during a given week."""

    participation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    process_id: uuid.UUID
    person_id: uuid.UUID
    week_start: date

    role_in_process: str  # owner | contributor | reviewer | blocked_by | blocking | escalated_to | approver | executor

    tasks_owned: int = 0
    tasks_contributed: int = 0
    reviews_done: int = 0
    escalations_caused: int = 0
    blockers_caused: int = 0
    avg_response_time_h: Optional[float] = None
    tasks_overdue_owned: int = 0
    ownership_pct: Optional[float] = None


class ProcessHealthScore(BaseModel):
    """Computed health score with anomaly flags."""

    score: float  # 0-100
    anomaly_flags: list[str] = Field(default_factory=list)
    component_scores: dict[str, float] = Field(default_factory=dict)


class CollectionStats(BaseModel):
    """Stats from a single collection run."""

    source_name: str
    process_id: uuid.UUID
    week_start: date
    metrics_collected: int = 0
    participations_collected: int = 0
    health_score: Optional[float] = None
    anomaly_flags: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
