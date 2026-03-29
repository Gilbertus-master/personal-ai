"""Selects a concrete fix strategy for a detected bottleneck."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import structlog

from app.analysis.perf_improver.bottleneck_detector import Bottleneck

log = structlog.get_logger("perf_improver.fix_planner")


@dataclass
class FixPlan:
    action: str  # human-readable description
    param_name: str  # env var or file to change
    old_value: str
    new_value: str
    change_type: str  # "env" or "file"
    file_path: Optional[str] = None


# Maps bottleneck_type → list of candidate fixes (tried in order)
FIX_STRATEGIES = {
    "slow_interpret": [
        {
            "param": "INTERPRETATION_CACHE_TTL",
            "change_type": "env",
            "default": "300",
            "target": "600",
            "desc": "Double interpretation cache TTL from 300s to 600s",
        },
    ],
    "slow_retrieve": [
        {
            "param": "ENABLE_TOOL_ROUTING",
            "change_type": "env",
            "default": "false",
            "target": "true",
            "desc": "Enable tool routing to narrow source groups",
        },
    ],
    "slow_answer": [
        {
            "param": "MAX_CONTEXT_CHARS",
            "change_type": "env",
            "default": "80000",
            "target": "60000",
            "desc": "Reduce max context chars from 80k to 60k",
        },
    ],
    "very_slow_query": [
        {
            "param": "MAX_CONTEXT_CHARS",
            "change_type": "env",
            "default": "80000",
            "target": "60000",
            "desc": "Reduce max context chars from 80k to 60k",
        },
    ],
    "low_cache": [
        {
            "param": "INTERPRETATION_CACHE_TTL",
            "change_type": "env",
            "default": "300",
            "target": "900",
            "desc": "Triple interpretation cache TTL from 300s to 900s",
        },
    ],
    "excessive_high_depth": [
        {
            "param": "INTERPRETATION_CACHE_TTL",
            "change_type": "env",
            "default": "300",
            "target": "600",
            "desc": "Increase cache TTL to reuse interpretations for repeated queries",
        },
    ],
}


def _get_current_env_value(param: str, default: str) -> str:
    """Read current value from environment (loaded from .env via dotenv)."""
    return os.getenv(param, default)


def _was_recently_applied(param: str, new_value: str) -> bool:
    """Check if this exact fix was already applied in the last 7 days."""
    from app.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM perf_improvement_journal
                WHERE param_changed = %s AND new_value = %s
                AND run_date > CURRENT_DATE - INTERVAL '7 days'
                """,
                (param, new_value),
            )
            return cur.fetchone()[0] > 0


def plan_fix(bottleneck: Bottleneck) -> Optional[FixPlan]:
    """Return a concrete fix plan for the bottleneck, or None if no fix available."""
    if bottleneck.type in ("none", "insufficient_data", "high_errors"):
        log.info("no_auto_fix", bottleneck=bottleneck.type, reason="not auto-fixable")
        return None

    strategies = FIX_STRATEGIES.get(bottleneck.type, [])
    if not strategies:
        log.info("no_strategy", bottleneck=bottleneck.type)
        return None

    for strategy in strategies:
        param = strategy["param"]
        target = strategy["target"]
        current = _get_current_env_value(param, strategy["default"])

        # Skip if already at target or beyond
        if current == target:
            log.info("already_at_target", param=param, value=current)
            continue

        # Skip if recently applied
        if _was_recently_applied(param, target):
            log.info("recently_applied", param=param, target=target)
            continue

        plan = FixPlan(
            action=strategy["desc"],
            param_name=param,
            old_value=current,
            new_value=target,
            change_type=strategy["change_type"],
        )
        log.info("fix_planned", action=plan.action, param=plan.param_name, old=plan.old_value, new=plan.new_value)
        return plan

    log.info("all_fixes_exhausted", bottleneck=bottleneck.type)
    return None
