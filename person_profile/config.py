"""Tunable parameters for the person_profile module."""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Tie-strength decay
# ---------------------------------------------------------------------------
DECAY_LAMBDA: float = float(os.getenv("PP_DECAY_LAMBDA", "0.03"))

# ---------------------------------------------------------------------------
# Tie-strength dimension weights (must sum to ~1.0 when sentiment available)
# ---------------------------------------------------------------------------
W_FREQUENCY: float = 0.25
W_RECENCY: float = 0.20
W_RECIPROCITY: float = 0.20
W_CHANNEL_DIV: float = 0.15
W_SENTIMENT: float = 0.20

# ---------------------------------------------------------------------------
# Tie-strength thresholds
# ---------------------------------------------------------------------------
MIN_INTERACTIONS_FOR_SCORE: int = 3
DEFAULT_WEAK_SCORE: float = 0.05
MAX_CHANNELS_NORM: int = 5  # channel diversity divisor

# Relationship labels
STRENGTH_CLOSE: float = 0.7
STRENGTH_STRONG: float = 0.5
STRENGTH_ACQUAINTANCE: float = 0.3
STRENGTH_WEAK: float = 0.1

# ---------------------------------------------------------------------------
# Time windows (days)
# ---------------------------------------------------------------------------
WINDOW_SHORT: int = int(os.getenv("PP_WINDOW_SHORT", "7"))
WINDOW_MEDIUM: int = int(os.getenv("PP_WINDOW_MEDIUM", "30"))
WINDOW_LONG: int = int(os.getenv("PP_WINDOW_LONG", "90"))
COMMUNICATION_PATTERN_WINDOW: int = 90

# ---------------------------------------------------------------------------
# Delta pipeline
# ---------------------------------------------------------------------------
WATERMARK_OVERLAP_HOURS: int = 1
PIPELINE_SOURCES: list[str] = [
    "identities",
    "demographics",
    "professional",
    "behavioral",
    "relationships",
    "trajectory",
    "network",
    "open_loops",
    "shared_context",
    "next_actions",
    "briefings",
]

# ---------------------------------------------------------------------------
# Next best actions
# ---------------------------------------------------------------------------
NBA_OPEN_LOOP_CRITICAL_DAYS: int = 3
NBA_OPEN_LOOP_OVERDUE_DAYS: int = 14
NBA_JOB_CHANGE_WINDOW_DAYS: int = 14
NBA_COOLING_MIN_DAYS: int = 30
NBA_NO_CONTACT_DAYS: int = 45
NBA_NO_CONTACT_MIN_TIE: float = 0.5

NBA_EXPIRE_HIGH_PRIORITY_DAYS: int = 7
NBA_EXPIRE_LOW_PRIORITY_DAYS: int = 14

# ---------------------------------------------------------------------------
# Briefing
# ---------------------------------------------------------------------------
BRIEFING_TTL_HOURS: int = int(os.getenv("PP_BRIEFING_TTL_HOURS", "24"))
BRIEFING_STALE_TIE_DELTA: float = 0.1

ANTHROPIC_MODEL: str = os.getenv(
    "PP_ANTHROPIC_MODEL",
    os.getenv("ANTHROPIC_EXTRACTION_MODEL", "claude-sonnet-4-5-20250514"),
)
ANTHROPIC_MAX_TOKENS: int = 1200
