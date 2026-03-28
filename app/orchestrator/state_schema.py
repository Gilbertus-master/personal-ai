"""Shared TypedDict state schemas for Gilbertus StateGraphs."""
from __future__ import annotations

from typing import TypedDict, Optional, Literal


class ActionState(TypedDict):
    """State for Action Pipeline graph."""

    # Input
    action_id: int
    action_type: str
    description: str
    draft_params: dict
    source: str

    # Routing
    status: Literal["pending", "approved", "rejected", "executed", "failed"]
    human_decision: Optional[Literal["approve", "reject", "edit"]]
    edit_text: Optional[str]

    # Output
    execution_result: Optional[dict]
    error: Optional[str]

    # Metadata
    proposed_at: Optional[str]
    decided_at: Optional[str]
    executed_at: Optional[str]
    retry_count: int


class BriefState(TypedDict):
    """State for Morning Brief generation graph (Faza 2)."""

    # Input
    date: str
    date_from: str
    date_to: str
    lookback_days: int

    # Data fetching (parallel nodes)
    events: list
    open_loops: list
    entities: list
    summaries: list
    calendar: list
    market: list
    competitors: list
    predictions: list
    alerts_result: Optional[dict]

    # Generation
    context: Optional[str]
    brief_text: Optional[str]
    summary_id: Optional[int]

    # Routing
    status: Literal["fetching", "building", "generating", "saving", "done", "no_data", "failed"]
    error: Optional[str]
