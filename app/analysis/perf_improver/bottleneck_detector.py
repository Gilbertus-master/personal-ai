"""Classifies the dominant bottleneck from aggregated ask_runs stats."""
from __future__ import annotations

from dataclasses import dataclass

import structlog

from app.analysis.perf_improver.query_analyzer import AskRunsStats

log = structlog.get_logger("perf_improver.bottleneck_detector")


@dataclass
class Bottleneck:
    type: str  # e.g. "slow_answer", "slow_interpret", "none"
    severity: str  # "critical", "high", "medium", "low", "none"
    detail: str  # human-readable explanation
    metric_value: float = 0.0


# Thresholds
INTERPRET_SLOW_MS = 3000
RETRIEVE_SLOW_MS = 5000
ANSWER_SLOW_MS = 15000
TOTAL_VERY_SLOW_MS = 30000
ERROR_RATE_THRESHOLD = 5.0
CACHE_HIT_THRESHOLD = 30.0
HIGH_DEPTH_THRESHOLD = 60.0


def detect(stats: AskRunsStats) -> Bottleneck:
    """Detect the most impactful bottleneck. Returns highest-priority one."""
    if stats.total_runs == 0:
        return Bottleneck("insufficient_data", "none", "No queries in analysis window")

    # Priority order: errors > very_slow > slow_answer > slow_retrieve > slow_interpret > low_cache > high_depth
    if stats.error_rate_pct > ERROR_RATE_THRESHOLD:
        return Bottleneck(
            "high_errors",
            "critical",
            f"Error rate {stats.error_rate_pct}% exceeds {ERROR_RATE_THRESHOLD}%",
            stats.error_rate_pct,
        )

    if stats.p95_ms > TOTAL_VERY_SLOW_MS:
        return Bottleneck(
            "very_slow_query",
            "high",
            f"P95 latency {stats.p95_ms}ms exceeds {TOTAL_VERY_SLOW_MS}ms",
            stats.p95_ms,
        )

    if stats.avg_answer_ms > ANSWER_SLOW_MS:
        return Bottleneck(
            "slow_answer",
            "high",
            f"Avg answer stage {stats.avg_answer_ms}ms exceeds {ANSWER_SLOW_MS}ms",
            stats.avg_answer_ms,
        )

    if stats.avg_retrieve_ms > RETRIEVE_SLOW_MS:
        return Bottleneck(
            "slow_retrieve",
            "medium",
            f"Avg retrieve stage {stats.avg_retrieve_ms}ms exceeds {RETRIEVE_SLOW_MS}ms",
            stats.avg_retrieve_ms,
        )

    if stats.avg_interpret_ms > INTERPRET_SLOW_MS:
        return Bottleneck(
            "slow_interpret",
            "medium",
            f"Avg interpret stage {stats.avg_interpret_ms}ms exceeds {INTERPRET_SLOW_MS}ms",
            stats.avg_interpret_ms,
        )

    if stats.cache_hit_rate_pct < CACHE_HIT_THRESHOLD and stats.total_runs >= 5:
        return Bottleneck(
            "low_cache",
            "low",
            f"Cache hit rate {stats.cache_hit_rate_pct}% below {CACHE_HIT_THRESHOLD}%",
            stats.cache_hit_rate_pct,
        )

    if stats.high_depth_pct > HIGH_DEPTH_THRESHOLD:
        return Bottleneck(
            "excessive_high_depth",
            "medium",
            f"High-depth queries at {stats.high_depth_pct}% (>{HIGH_DEPTH_THRESHOLD}%)",
            stats.high_depth_pct,
        )

    return Bottleneck(
        "none",
        "none",
        f"All metrics within thresholds (avg={stats.avg_latency_ms}ms, p95={stats.p95_ms}ms)",
    )
