"""Feedback & Quality API — evaluation trends, weak areas, optimization report."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.analysis.feedback_persistence import get_evaluation_trends, get_weak_areas
from app.analysis.threshold_optimizer import generate_optimization_report

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("/trends")
def feedback_trends(days: int = Query(default=30, ge=1, le=365)) -> dict:
    """Get answer evaluation score trends over the last N days."""
    return get_evaluation_trends(days=days)


@router.get("/weak-areas")
def feedback_weak_areas(
    threshold: float = Query(default=0.5, ge=0.0, le=1.0),
    days: int = Query(default=30, ge=1, le=365),
) -> list:
    """Identify question types and sources with consistently low eval scores."""
    return get_weak_areas(threshold=threshold, days=days)


@router.get("/optimization-report")
def feedback_optimization_report(days: int = Query(default=30, ge=1, le=365)) -> dict:
    """Generate comprehensive optimization report for alerts and brief sections."""
    return generate_optimization_report(days=days)
