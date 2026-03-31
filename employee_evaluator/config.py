"""Tunable parameters for the employee_evaluator module."""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# AI model
# ---------------------------------------------------------------------------
ANTHROPIC_MODEL: str = os.getenv(
    "EE_ANTHROPIC_MODEL",
    os.getenv("ANTHROPIC_EXTRACTION_MODEL", "claude-haiku-4-5-20251001"),
)
ANTHROPIC_MAX_TOKENS: int = int(os.getenv("EE_ANTHROPIC_MAX_TOKENS", "2000"))

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
MIN_WEEKS_FULL_CONFIDENCE: int = 8
SCORE_MIN: float = 1.0
SCORE_MAX: float = 5.0
BENCHMARK_SCORE: float = 3.0  # what benchmark values map to

# ---------------------------------------------------------------------------
# Overall labels
# ---------------------------------------------------------------------------
LABEL_EXCEPTIONAL: str = "exceptional"
LABEL_EXCEEDS: str = "exceeds_expectations"
LABEL_MEETS: str = "meets_expectations"
LABEL_DEVELOPING: str = "developing"
LABEL_BELOW: str = "below_expectations"

# ---------------------------------------------------------------------------
# 9-box
# ---------------------------------------------------------------------------
NINE_BOX_HIGH_THRESHOLD: float = 3.5
NINE_BOX_LOW_THRESHOLD: float = 2.5

# ---------------------------------------------------------------------------
# Data retention
# ---------------------------------------------------------------------------
DEFAULT_RETENTION_DAYS: int = int(os.getenv("EE_RETENTION_DAYS", "730"))

# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------
BATCH_COMMIT_EVERY: int = 10

# ---------------------------------------------------------------------------
# Evaluation modes
# ---------------------------------------------------------------------------
MODE_DEVELOPMENT: str = "development"
MODE_PERFORMANCE: str = "performance"
