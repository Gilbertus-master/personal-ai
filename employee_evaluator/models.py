"""Pydantic models for employee evaluation data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID


@dataclass
class RawSignal:
    """A single week of raw signal data from employee_signals."""

    person_id: UUID
    week_start: date
    teams_messages_sent: int = 0
    teams_messages_received: int = 0
    teams_reactions_given: int = 0
    teams_meetings_attended: int = 0
    teams_meetings_organized: int = 0
    emails_sent: int = 0
    emails_received: int = 0
    emails_avg_response_hours: float | None = None
    commits_count: int = 0
    commits_lines_added: int = 0
    commits_lines_removed: int = 0
    commits_pr_reviews: int = 0
    tasks_created: int = 0
    tasks_completed: int = 0
    tasks_assigned: int = 0
    tasks_overdue: int = 0
    tasks_blockers_resolved: int = 0
    docs_created: int = 0
    docs_edited: int = 0
    hr_absences_days: float = 0
    hr_training_hours: float = 0
    hr_feedback_given: int = 0
    hr_feedback_received: int = 0


@dataclass
class AggregatedSignals:
    """Aggregated signals over an evaluation period."""

    person_id: UUID
    weeks_count: int = 0
    data_completeness: float = 0.0

    # Averages per week
    avg_messages_sent: float = 0.0
    avg_messages_received: float = 0.0
    avg_meetings_attended: float = 0.0
    avg_meetings_organized: float = 0.0
    avg_emails_sent: float = 0.0
    avg_emails_received: float = 0.0
    avg_response_hours: float | None = None
    avg_commits: float = 0.0
    avg_pr_reviews: float = 0.0
    avg_tasks_completed: float = 0.0
    avg_tasks_created: float = 0.0
    avg_docs_created: float = 0.0

    # Totals
    total_tasks_completed: int = 0
    total_tasks_assigned: int = 0
    total_tasks_overdue: int = 0
    total_tasks_created: int = 0
    total_blockers_resolved: int = 0
    total_commits: int = 0
    total_pr_reviews: int = 0
    total_docs_created: int = 0
    total_docs_edited: int = 0
    total_feedback_given: int = 0
    total_feedback_received: int = 0
    total_training_hours: float = 0.0
    total_reactions_given: int = 0

    # Trends (positive = improving)
    trend_tasks_completed: float = 0.0
    trend_messages_sent: float = 0.0
    trend_commits: float = 0.0
    trend_response_hours: float = 0.0


@dataclass
class CompetencyScore:
    """Score for a single competency dimension."""

    name: str
    score: float | None = None  # 1.0-5.0, None if no data
    confidence: float = 0.0     # 0.0-1.0
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class NineBoxPosition:
    """9-box grid position."""

    performance_level: str  # 'high', 'medium', 'low'
    potential_level: str    # 'high', 'medium', 'low'
    label: str              # 'Star', 'High Potential', etc.


@dataclass
class EmployeeEvaluationInput:
    """All input data needed for an evaluation."""

    person_id: UUID
    display_name: str
    role_name: str | None = None
    seniority_level: str = "mid"
    signals: AggregatedSignals | None = None
    profile_data: dict[str, Any] = field(default_factory=dict)
    relationship_data: dict[str, Any] = field(default_factory=dict)
    previous_scores: dict[str, float] | None = None


@dataclass
class EvaluationResult:
    """Complete evaluation output."""

    person_id: UUID
    cycle_id: UUID
    display_name: str
    competency_scores: list[CompetencyScore] = field(default_factory=list)
    overall_score: float | None = None
    overall_label: str | None = None
    potential_score: float | None = None
    flight_risk_score: float | None = None
    nine_box: NineBoxPosition | None = None
    data_completeness: float = 0.0
    report: dict[str, Any] | None = None
    requires_human_review: bool = True
    errors: list[str] = field(default_factory=list)
