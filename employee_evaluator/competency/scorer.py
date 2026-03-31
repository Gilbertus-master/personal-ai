"""Score 8 competency dimensions from aggregated signals and profile data.

Each competency returns a CompetencyScore with:
- score: 1.0-5.0 (or None if no data)
- confidence: 0.0-1.0 (full after 8 weeks of data)
- evidence: dict of metrics used

Key rule: No data -> confidence=0, score=None (NOT a bad score).
"""

from __future__ import annotations

from typing import Any

import structlog

from ..config import MIN_WEEKS_FULL_CONFIDENCE, SCORE_MAX, SCORE_MIN, BENCHMARK_SCORE
from ..models import AggregatedSignals, CompetencyScore
from .benchmarks import get_benchmarks

log = structlog.get_logger("employee_evaluator.scorer")


def score_all_competencies(
    signals: AggregatedSignals,
    profile_data: dict[str, Any],
    relationship_data: dict[str, Any],
    seniority_level: str = "mid",
    previous_scores: dict[str, float] | None = None,
) -> list[CompetencyScore]:
    """Score all 8 competencies and return list of CompetencyScore."""
    benchmarks = get_benchmarks(seniority_level)
    base_confidence = _base_confidence(signals.weeks_count)

    scores = [
        _score_delivery(signals, benchmarks, base_confidence),
        _score_collaboration(signals, profile_data, relationship_data, benchmarks, base_confidence),
        _score_communication(signals, profile_data, benchmarks, base_confidence),
        _score_initiative(signals, benchmarks, base_confidence),
        _score_knowledge(signals, profile_data, benchmarks, base_confidence),
        _score_leadership(signals, profile_data, benchmarks, base_confidence),
        _score_growth(signals, previous_scores, benchmarks, base_confidence),
        _score_relationships(relationship_data, profile_data, base_confidence),
    ]

    log.info(
        "competencies_scored",
        scored_count=sum(1 for s in scores if s.score is not None),
        avg_confidence=round(
            sum(s.confidence for s in scores) / max(len(scores), 1), 2
        ),
    )
    return scores


def _base_confidence(weeks_count: int) -> float:
    """Confidence based on data volume: full after MIN_WEEKS_FULL_CONFIDENCE weeks."""
    return min(1.0, weeks_count / MIN_WEEKS_FULL_CONFIDENCE)


def _ratio_to_score(actual: float, benchmark: float, invert: bool = False) -> float:
    """Map a ratio to 1.0-5.0 scale relative to benchmark (=3.0).

    If invert=True, lower actual = better (e.g., response time).
    """
    if benchmark <= 0:
        return BENCHMARK_SCORE

    if invert:
        # Lower is better: ratio > 1 means worse
        ratio = benchmark / actual if actual > 0 else 1.5
    else:
        ratio = actual / benchmark

    # ratio=1.0 -> 3.0, ratio=1.5 -> 4.5, ratio=0.5 -> 1.5
    score = BENCHMARK_SCORE + (ratio - 1.0) * 3.0
    return max(SCORE_MIN, min(SCORE_MAX, score))


def _has_signal_data(signals: AggregatedSignals, *fields: str) -> bool:
    """Check if at least one field has non-zero data."""
    return any(getattr(signals, f, 0) not in (0, 0.0, None) for f in fields)


# ── 1. Delivery ──────────────────────────────────────────────────────

def _score_delivery(
    signals: AggregatedSignals,
    benchmarks: dict[str, float],
    base_confidence: float,
) -> CompetencyScore:
    """Tasks completed ratio, velocity, overdue ratio."""
    if not _has_signal_data(signals, "total_tasks_assigned", "total_tasks_completed"):
        return CompetencyScore(name="delivery", confidence=0.0, evidence={"reason": "no_task_data"})

    completed_ratio = (
        signals.total_tasks_completed / signals.total_tasks_assigned
        if signals.total_tasks_assigned > 0
        else 0.0
    )
    overdue_ratio = (
        signals.total_tasks_overdue / signals.total_tasks_assigned
        if signals.total_tasks_assigned > 0
        else 0.0
    )

    score_completion = _ratio_to_score(completed_ratio, benchmarks["tasks_completed_ratio"])
    # Overdue penalty: each 10% overdue reduces score by 0.5
    penalty = overdue_ratio * 5.0
    final_score = max(SCORE_MIN, score_completion - penalty)

    evidence = {
        "tasks_completed": signals.total_tasks_completed,
        "tasks_assigned": signals.total_tasks_assigned,
        "completed_ratio": round(completed_ratio, 3),
        "overdue_ratio": round(overdue_ratio, 3),
        "trend": round(signals.trend_tasks_completed, 3),
    }

    # Adjust for trend (up to +/- 0.3)
    trend_adj = min(0.3, max(-0.3, signals.trend_tasks_completed * 0.3))
    final_score = max(SCORE_MIN, min(SCORE_MAX, final_score + trend_adj))

    return CompetencyScore(
        name="delivery",
        score=round(final_score, 2),
        confidence=base_confidence,
        evidence=evidence,
    )


# ── 2. Collaboration ────────────────────────────────────────────────

def _score_collaboration(
    signals: AggregatedSignals,
    profile_data: dict[str, Any],
    relationship_data: dict[str, Any],
    benchmarks: dict[str, float],
    base_confidence: float,
) -> CompetencyScore:
    """PR reviews, response ratio, network ties, reactions."""
    evidence: dict[str, Any] = {}
    sub_scores: list[float] = []
    data_points = 0

    # PR review ratio
    if _has_signal_data(signals, "total_pr_reviews", "total_commits"):
        review_ratio = (
            signals.total_pr_reviews / signals.total_commits
            if signals.total_commits > 0
            else 0.0
        )
        sub_scores.append(_ratio_to_score(review_ratio, benchmarks["pr_review_ratio"]))
        evidence["pr_review_ratio"] = round(review_ratio, 3)
        data_points += 1

    # Response ratio (messages received vs sent)
    if _has_signal_data(signals, "avg_messages_sent", "avg_messages_received"):
        response_ratio = (
            signals.avg_messages_sent / signals.avg_messages_received
            if signals.avg_messages_received > 0
            else 0.0
        )
        sub_scores.append(_ratio_to_score(min(response_ratio, 1.5), 0.8))
        evidence["response_ratio"] = round(response_ratio, 3)
        data_points += 1

    # Reactions given (engagement proxy)
    if _has_signal_data(signals, "total_reactions_given"):
        weekly_reactions = signals.total_reactions_given / max(signals.weeks_count, 1)
        sub_scores.append(min(SCORE_MAX, BENCHMARK_SCORE + (weekly_reactions - 5.0) * 0.2))
        evidence["weekly_reactions"] = round(weekly_reactions, 1)
        data_points += 1

    # Network tie strength from relationships
    avg_tie = relationship_data.get("avg_health", 0)
    if avg_tie > 0:
        sub_scores.append(_ratio_to_score(avg_tie, 0.5))
        evidence["avg_tie_strength"] = round(avg_tie, 3)
        data_points += 1

    if not sub_scores:
        return CompetencyScore(name="collaboration", confidence=0.0, evidence={"reason": "no_data"})

    final_score = sum(sub_scores) / len(sub_scores)
    confidence = base_confidence * min(1.0, data_points / 3.0)

    return CompetencyScore(
        name="collaboration",
        score=round(max(SCORE_MIN, min(SCORE_MAX, final_score)), 2),
        confidence=round(confidence, 2),
        evidence=evidence,
    )


# ── 3. Communication ────────────────────────────────────────────────

def _score_communication(
    signals: AggregatedSignals,
    profile_data: dict[str, Any],
    benchmarks: dict[str, float],
    base_confidence: float,
) -> CompetencyScore:
    """Response time, meeting participation, consistency."""
    evidence: dict[str, Any] = {}
    sub_scores: list[float] = []
    data_points = 0

    # Response time
    if signals.avg_response_hours is not None:
        sub_scores.append(
            _ratio_to_score(signals.avg_response_hours, benchmarks["response_time_hours"], invert=True)
        )
        evidence["avg_response_hours"] = round(signals.avg_response_hours, 1)
        data_points += 1

    # Meeting participation
    if _has_signal_data(signals, "avg_meetings_attended"):
        sub_scores.append(
            _ratio_to_score(signals.avg_meetings_attended, benchmarks["meeting_participation"] * 10)
        )
        evidence["avg_meetings_attended"] = round(signals.avg_meetings_attended, 1)
        data_points += 1

    # Communication consistency from profile
    comm = profile_data.get("communication")
    if comm and comm.get("response_consistency") is not None:
        consistency = comm["response_consistency"]
        sub_scores.append(_ratio_to_score(consistency, 0.7))
        evidence["response_consistency"] = round(consistency, 3)
        data_points += 1

    if not sub_scores:
        return CompetencyScore(name="communication", confidence=0.0, evidence={"reason": "no_data"})

    final_score = sum(sub_scores) / len(sub_scores)
    confidence = base_confidence * min(1.0, data_points / 2.0)

    return CompetencyScore(
        name="communication",
        score=round(max(SCORE_MIN, min(SCORE_MAX, final_score)), 2),
        confidence=round(confidence, 2),
        evidence=evidence,
    )


# ── 4. Initiative ───────────────────────────────────────────────────

def _score_initiative(
    signals: AggregatedSignals,
    benchmarks: dict[str, float],
    base_confidence: float,
) -> CompetencyScore:
    """Tasks created ratio, docs created, blockers resolved."""
    evidence: dict[str, Any] = {}
    sub_scores: list[float] = []
    data_points = 0

    # Tasks created / assigned ratio
    if _has_signal_data(signals, "total_tasks_created", "total_tasks_assigned"):
        initiative_ratio = (
            signals.total_tasks_created / signals.total_tasks_assigned
            if signals.total_tasks_assigned > 0
            else 0.0
        )
        sub_scores.append(_ratio_to_score(initiative_ratio, benchmarks["initiative_ratio"]))
        evidence["initiative_ratio"] = round(initiative_ratio, 3)
        data_points += 1

    # Docs created per month
    if _has_signal_data(signals, "total_docs_created"):
        months = max(signals.weeks_count / 4.33, 1)
        docs_per_month = signals.total_docs_created / months
        sub_scores.append(_ratio_to_score(docs_per_month, benchmarks["docs_per_month"]))
        evidence["docs_per_month"] = round(docs_per_month, 1)
        data_points += 1

    # Blockers resolved
    if _has_signal_data(signals, "total_blockers_resolved"):
        weekly_blockers = signals.total_blockers_resolved / max(signals.weeks_count, 1)
        sub_scores.append(min(SCORE_MAX, BENCHMARK_SCORE + weekly_blockers * 1.0))
        evidence["weekly_blockers_resolved"] = round(weekly_blockers, 2)
        data_points += 1

    if not sub_scores:
        return CompetencyScore(name="initiative", confidence=0.0, evidence={"reason": "no_data"})

    final_score = sum(sub_scores) / len(sub_scores)
    confidence = base_confidence * min(1.0, data_points / 2.0)

    return CompetencyScore(
        name="initiative",
        score=round(max(SCORE_MIN, min(SCORE_MAX, final_score)), 2),
        confidence=round(confidence, 2),
        evidence=evidence,
    )


# ── 5. Knowledge ────────────────────────────────────────────────────

def _score_knowledge(
    signals: AggregatedSignals,
    profile_data: dict[str, Any],
    benchmarks: dict[str, float],
    base_confidence: float,
) -> CompetencyScore:
    """Proxy from review quality, docs, training. Lower confidence if no direct data."""
    evidence: dict[str, Any] = {}
    sub_scores: list[float] = []
    data_points = 0

    # PR reviews as proxy for knowledge sharing
    if _has_signal_data(signals, "total_pr_reviews"):
        weekly_reviews = signals.total_pr_reviews / max(signals.weeks_count, 1)
        sub_scores.append(min(SCORE_MAX, BENCHMARK_SCORE + (weekly_reviews - 2.0) * 0.5))
        evidence["weekly_pr_reviews"] = round(weekly_reviews, 2)
        data_points += 1

    # Docs created as knowledge contribution
    if _has_signal_data(signals, "total_docs_created"):
        months = max(signals.weeks_count / 4.33, 1)
        docs_per_month = signals.total_docs_created / months
        sub_scores.append(_ratio_to_score(docs_per_month, benchmarks["docs_per_month"]))
        evidence["docs_per_month"] = round(docs_per_month, 1)
        data_points += 1

    # Training hours
    if _has_signal_data(signals, "total_training_hours"):
        monthly_training = signals.total_training_hours / max(signals.weeks_count / 4.33, 1)
        sub_scores.append(min(SCORE_MAX, BENCHMARK_SCORE + (monthly_training - 4.0) * 0.25))
        evidence["monthly_training_hours"] = round(monthly_training, 1)
        data_points += 1

    # Skills from profile
    prof = profile_data.get("professional")
    if prof and prof.get("skills"):
        skills = prof["skills"]
        skill_count = len(skills) if isinstance(skills, list) else 0
        if skill_count > 0:
            sub_scores.append(min(SCORE_MAX, BENCHMARK_SCORE + (skill_count - 5) * 0.2))
            evidence["skills_count"] = skill_count
            data_points += 1

    if not sub_scores:
        return CompetencyScore(name="knowledge", confidence=0.0, evidence={"reason": "no_direct_data"})

    final_score = sum(sub_scores) / len(sub_scores)
    # Knowledge is inherently lower confidence (proxy metrics)
    confidence = base_confidence * min(1.0, data_points / 3.0) * 0.8

    return CompetencyScore(
        name="knowledge",
        score=round(max(SCORE_MIN, min(SCORE_MAX, final_score)), 2),
        confidence=round(confidence, 2),
        evidence=evidence,
    )


# ── 6. Leadership ───────────────────────────────────────────────────

def _score_leadership(
    signals: AggregatedSignals,
    profile_data: dict[str, Any],
    benchmarks: dict[str, float],
    base_confidence: float,
) -> CompetencyScore:
    """Influence score, centrality, meetings organized, feedback given."""
    evidence: dict[str, Any] = {}
    sub_scores: list[float] = []
    data_points = 0

    # Network influence
    network = profile_data.get("network")
    if network:
        influence = network.get("influence_score")
        if influence is not None and influence > 0:
            sub_scores.append(_ratio_to_score(influence, 0.5))
            evidence["influence_score"] = round(influence, 3)
            data_points += 1

        centrality = network.get("degree_centrality")
        if centrality is not None and centrality > 0:
            sub_scores.append(_ratio_to_score(centrality, 0.3))
            evidence["degree_centrality"] = round(centrality, 3)
            data_points += 1

        is_broker = network.get("is_broker", False)
        evidence["is_broker"] = is_broker
        if is_broker:
            sub_scores.append(4.0)
            data_points += 1

    # Meetings organized
    if _has_signal_data(signals, "avg_meetings_organized"):
        org_ratio = (
            signals.avg_meetings_organized / signals.avg_meetings_attended
            if signals.avg_meetings_attended > 0
            else 0.0
        )
        sub_scores.append(
            _ratio_to_score(org_ratio, benchmarks["meetings_organized_ratio"])
        )
        evidence["meetings_organized_ratio"] = round(org_ratio, 3)
        data_points += 1

    # Feedback given
    if _has_signal_data(signals, "total_feedback_given"):
        months = max(signals.weeks_count / 4.33, 1)
        feedback_per_month = signals.total_feedback_given / months
        sub_scores.append(
            _ratio_to_score(feedback_per_month, benchmarks["feedback_given_per_month"])
        )
        evidence["feedback_per_month"] = round(feedback_per_month, 1)
        data_points += 1

    if not sub_scores:
        return CompetencyScore(name="leadership", confidence=0.0, evidence={"reason": "no_data"})

    final_score = sum(sub_scores) / len(sub_scores)
    confidence = base_confidence * min(1.0, data_points / 3.0)

    return CompetencyScore(
        name="leadership",
        score=round(max(SCORE_MIN, min(SCORE_MAX, final_score)), 2),
        confidence=round(confidence, 2),
        evidence=evidence,
    )


# ── 7. Growth ────────────────────────────────────────────────────────

def _score_growth(
    signals: AggregatedSignals,
    previous_scores: dict[str, float] | None,
    benchmarks: dict[str, float],
    base_confidence: float,
) -> CompetencyScore:
    """Trend analysis + comparison to previous cycle."""
    evidence: dict[str, Any] = {}
    sub_scores: list[float] = []
    data_points = 0

    # Metric trends
    trends = {
        "tasks": signals.trend_tasks_completed,
        "messages": signals.trend_messages_sent,
        "commits": signals.trend_commits,
    }
    positive_trends = sum(1 for v in trends.values() if v > 0.05)
    negative_trends = sum(1 for v in trends.values() if v < -0.05)
    trend_count = sum(1 for v in trends.values() if abs(v) > 0.01)

    if trend_count > 0:
        # Score based on ratio of positive to negative trends
        trend_score = BENCHMARK_SCORE + (positive_trends - negative_trends) * 0.5
        sub_scores.append(max(SCORE_MIN, min(SCORE_MAX, trend_score)))
        evidence["trends"] = {k: round(v, 3) for k, v in trends.items()}
        evidence["positive_trends"] = positive_trends
        evidence["negative_trends"] = negative_trends
        data_points += 1

    # Training hours as growth indicator
    if _has_signal_data(signals, "total_training_hours"):
        monthly_training = signals.total_training_hours / max(signals.weeks_count / 4.33, 1)
        sub_scores.append(min(SCORE_MAX, BENCHMARK_SCORE + (monthly_training - 2.0) * 0.3))
        evidence["monthly_training"] = round(monthly_training, 1)
        data_points += 1

    # Comparison to previous cycle
    if previous_scores:
        improvements = 0
        total_compared = 0
        for name, prev_score in previous_scores.items():
            total_compared += 1
            # We don't have current individual scores here, so use trends as proxy
            if trends.get("tasks", 0) > 0 or trends.get("commits", 0) > 0:
                improvements += 1
        if total_compared > 0:
            improvement_ratio = improvements / total_compared
            sub_scores.append(BENCHMARK_SCORE + (improvement_ratio - 0.5) * 2.0)
            evidence["improvement_ratio"] = round(improvement_ratio, 2)
            data_points += 1

    if not sub_scores:
        return CompetencyScore(name="growth", confidence=0.0, evidence={"reason": "no_trend_data"})

    final_score = sum(sub_scores) / len(sub_scores)
    confidence = base_confidence * min(1.0, data_points / 2.0) * 0.9

    return CompetencyScore(
        name="growth",
        score=round(max(SCORE_MIN, min(SCORE_MAX, final_score)), 2),
        confidence=round(confidence, 2),
        evidence=evidence,
    )


# ── 8. Relationships ────────────────────────────────────────────────

def _score_relationships(
    relationship_data: dict[str, Any],
    profile_data: dict[str, Any],
    base_confidence: float,
) -> CompetencyScore:
    """Average relationship health, growing/cooling counts, open loops."""
    evidence: dict[str, Any] = {}
    sub_scores: list[float] = []
    data_points = 0

    avg_health = relationship_data.get("avg_health", 0)
    if avg_health > 0:
        sub_scores.append(_ratio_to_score(avg_health, 0.5))
        evidence["avg_health"] = round(avg_health, 3)
        data_points += 1

    growing = relationship_data.get("growing_count", 0)
    cooling = relationship_data.get("cooling_count", 0)
    if growing + cooling > 0:
        health_ratio = growing / (growing + cooling) if (growing + cooling) > 0 else 0.5
        sub_scores.append(_ratio_to_score(health_ratio, 0.6))
        evidence["growing_count"] = growing
        evidence["cooling_count"] = cooling
        data_points += 1

    # Open loops (unresolved = negative signal)
    open_loops = profile_data.get("open_loops", [])
    if open_loops:
        open_count = len(open_loops)
        stale_count = sum(1 for ol in open_loops if ol.get("status") == "stale")
        loop_penalty = min(2.0, (stale_count * 0.3 + open_count * 0.1))
        sub_scores.append(max(SCORE_MIN, BENCHMARK_SCORE + 1.0 - loop_penalty))
        evidence["open_loops"] = open_count
        evidence["stale_loops"] = stale_count
        data_points += 1

    total_relationships = relationship_data.get("total_relationships", 0)
    if total_relationships > 0:
        evidence["total_relationships"] = total_relationships
        data_points += 1

    if not sub_scores:
        return CompetencyScore(name="relationships", confidence=0.0, evidence={"reason": "no_relationship_data"})

    final_score = sum(sub_scores) / len(sub_scores)
    confidence = base_confidence * min(1.0, data_points / 2.0) if base_confidence > 0 else min(1.0, data_points / 3.0)

    return CompetencyScore(
        name="relationships",
        score=round(max(SCORE_MIN, min(SCORE_MAX, final_score)), 2),
        confidence=round(confidence, 2),
        evidence=evidence,
    )
