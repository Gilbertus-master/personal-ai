"""Default benchmarks per seniority level.

Each benchmark value represents what maps to score=3.0 ("meets expectations").
Higher seniority = higher expectations.
"""

from __future__ import annotations


# Benchmarks: values that map to a 3.0 score
# Keys match the metric names used in scorer.py
DEFAULT_BENCHMARKS: dict[str, dict[str, float]] = {
    "junior": {
        "tasks_completed_ratio": 0.65,
        "response_time_hours": 6.0,
        "pr_review_ratio": 0.2,
        "meeting_participation": 0.60,
        "docs_per_month": 1.0,
        "initiative_ratio": 0.10,
        "meetings_organized_ratio": 0.05,
        "feedback_given_per_month": 1.0,
    },
    "mid": {
        "tasks_completed_ratio": 0.75,
        "response_time_hours": 4.0,
        "pr_review_ratio": 0.5,
        "meeting_participation": 0.70,
        "docs_per_month": 2.0,
        "initiative_ratio": 0.20,
        "meetings_organized_ratio": 0.10,
        "feedback_given_per_month": 2.0,
    },
    "senior": {
        "tasks_completed_ratio": 0.85,
        "response_time_hours": 3.0,
        "pr_review_ratio": 0.7,
        "meeting_participation": 0.80,
        "docs_per_month": 3.0,
        "initiative_ratio": 0.30,
        "meetings_organized_ratio": 0.20,
        "feedback_given_per_month": 3.0,
    },
    "lead": {
        "tasks_completed_ratio": 0.80,
        "response_time_hours": 3.0,
        "pr_review_ratio": 0.8,
        "meeting_participation": 0.85,
        "docs_per_month": 4.0,
        "initiative_ratio": 0.35,
        "meetings_organized_ratio": 0.30,
        "feedback_given_per_month": 4.0,
    },
    "director": {
        "tasks_completed_ratio": 0.75,
        "response_time_hours": 4.0,
        "pr_review_ratio": 0.5,
        "meeting_participation": 0.90,
        "docs_per_month": 3.0,
        "initiative_ratio": 0.40,
        "meetings_organized_ratio": 0.40,
        "feedback_given_per_month": 5.0,
    },
    "executive": {
        "tasks_completed_ratio": 0.70,
        "response_time_hours": 8.0,
        "pr_review_ratio": 0.3,
        "meeting_participation": 0.85,
        "docs_per_month": 2.0,
        "initiative_ratio": 0.50,
        "meetings_organized_ratio": 0.50,
        "feedback_given_per_month": 4.0,
    },
}


def get_benchmarks(seniority_level: str = "mid") -> dict[str, float]:
    """Get benchmark values for a seniority level.

    Returns default 'mid' benchmarks for unknown levels.
    """
    return DEFAULT_BENCHMARKS.get(seniority_level, DEFAULT_BENCHMARKS["mid"]).copy()
