"""Pydantic models for process discovery."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProcessEvent(BaseModel):
    """A single state transition event from any source system."""

    event_id: Optional[UUID] = None
    source: str  # jira | crm | helpdesk | github | email
    entity_type: str  # ticket | deal | pr | email_thread
    entity_id: str
    from_state: Optional[str] = None
    to_state: str
    state_group: Optional[str] = None
    actor_person_id: Optional[UUID] = None
    occurred_at: datetime
    duration_in_prev_state_h: Optional[float] = None
    context_tags: list[str] = Field(default_factory=list)
    project_key: Optional[str] = None
    priority: Optional[str] = None
    raw_data: Optional[dict[str, Any]] = None


class ProcessCandidate(BaseModel):
    """A discovered state-transition pattern awaiting review."""

    candidate_id: Optional[UUID] = None
    pattern_hash: str
    sequence: list[str]
    source: str
    entity_type: str
    project_keys: list[str] = Field(default_factory=list)
    occurrences_count: int
    occurrences_per_week: float
    avg_duration_h: Optional[float] = None
    p90_duration_h: Optional[float] = None
    unique_actors_count: Optional[int] = None
    suggested_name: Optional[str] = None
    suggested_description: Optional[str] = None
    suggested_type: Optional[str] = None
    suggested_metrics: Optional[dict[str, Any]] = None
    llm_confidence: Optional[float] = None
    status: str = "pending"
    merged_into_process_id: Optional[UUID] = None
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class DiscoveryResult(BaseModel):
    """Summary statistics from a discovery run."""

    events_collected: int = 0
    sequences_found: int = 0
    candidates_created: int = 0
