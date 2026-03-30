"""Fetches and aggregates ask_runs stats for a 24h window."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger("perf_improver.query_analyzer")


@dataclass
class AskRunsStats:
    total_runs: int = 0
    avg_latency_ms: int = 0
    p50_ms: int = 0
    p95_ms: int = 0
    max_ms: int = 0
    error_count: int = 0
    error_rate_pct: float = 0.0
    cache_hit_count: int = 0
    cache_hit_rate_pct: float = 0.0
    avg_interpret_ms: int = 0
    avg_retrieve_ms: int = 0
    avg_answer_ms: int = 0
    high_depth_pct: float = 0.0
    avg_context_chars: int = 0
    slowest_queries: list = field(default_factory=list)


def fetch_24h_stats(hours: int = 24) -> AskRunsStats:
    """Fetch aggregated performance stats from ask_runs for the last N hours."""
    stats = AskRunsStats()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Basic stats, stage averages, and high_depth_pct in one query
            cur.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COALESCE(ROUND(AVG(latency_ms)), 0) as avg_ms,
                    COALESCE(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms), 0) as p50,
                    COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms), 0) as p95,
                    COALESCE(MAX(latency_ms), 0) as max_ms,
                    COUNT(*) FILTER (WHERE error_flag) as errors,
                    COUNT(*) FILTER (WHERE cache_hit) as cache_hits,
                    COALESCE(ROUND(AVG((stage_ms->>'interpret')::int)), 0),
                    COALESCE(ROUND(AVG((stage_ms->>'retrieve')::int)), 0),
                    COALESCE(ROUND(AVG((stage_ms->>'answer')::int)), 0),
                    ROUND(100.0 * COUNT(*) FILTER (WHERE analysis_depth = 'high') / NULLIF(COUNT(*), 0), 1)
                FROM ask_runs
                WHERE created_at > %s
                """,
                (cutoff,),
            )
            rows = cur.fetchall()
            row = rows[0]
            stats.total_runs = row[0]
            if stats.total_runs == 0:
                log.info("no_ask_runs_in_window", hours=hours)
                return stats

            stats.avg_latency_ms = int(row[1])
            stats.p50_ms = int(row[2])
            stats.p95_ms = int(row[3])
            stats.max_ms = int(row[4])
            stats.error_count = row[5]
            stats.cache_hit_count = row[6]
            stats.error_rate_pct = round(100.0 * stats.error_count / stats.total_runs, 1)
            stats.cache_hit_rate_pct = round(100.0 * stats.cache_hit_count / stats.total_runs, 1)
            stats.avg_interpret_ms = int(row[7])
            stats.avg_retrieve_ms = int(row[8])
            stats.avg_answer_ms = int(row[9])
            stats.high_depth_pct = float(row[10] or 0)

            # Slowest 5 queries
            cur.execute(
                """
                SELECT id, query_text, latency_ms, stage_ms, analysis_depth, created_at
                FROM ask_runs
                WHERE created_at > %s
                ORDER BY latency_ms DESC NULLS LAST
                LIMIT 5
                """,
                (cutoff,),
            )
            stats.slowest_queries = [
                {
                    "id": r[0],
                    "query": r[1][:100] if r[1] else "",
                    "latency_ms": r[2],
                    "stage_ms": r[3],
                    "depth": r[4],
                }
                for r in cur.fetchall()
            ]

    log.info(
        "stats_fetched",
        total=stats.total_runs,
        avg_ms=stats.avg_latency_ms,
        p95_ms=stats.p95_ms,
        bottleneck_answer_ms=stats.avg_answer_ms,
    )
    return stats
