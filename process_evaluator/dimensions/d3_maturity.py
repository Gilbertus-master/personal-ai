"""D3: Maturity — Process Maturity Level (PML) from survey or estimation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import psycopg
import structlog
from psycopg.rows import dict_row

from ..models import DimensionScore

log = structlog.get_logger("process_evaluator.d3_maturity")

# PML levels: 1=Initial, 2=Repeatable, 3=Defined, 4=Managed, 5=Optimizing
PML_SCORE_MAP = {1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0}


def compute_d3(
    process_id: UUID,
    conn: psycopg.Connection,
) -> DimensionScore:
    """Compute maturity dimension.

    Priority:
    1. Recent maturity survey (within 90 days) — high confidence
    2. Estimated from data proxies — low confidence (0.3)
    """
    # ── Check for recent survey ─────────────────────────────────────
    survey_result = _get_recent_survey(process_id, conn)

    if survey_result is not None:
        pml = survey_result["process_maturity_level"]
        score = PML_SCORE_MAP.get(pml, 3.0)
        return DimensionScore(
            name="maturity",
            score=score,
            confidence=0.9,
            evidence={
                "source": "survey",
                "pml_level": pml,
                "survey_date": str(survey_result["maturity_survey_date"]),
            },
            sub_scores={"pml": float(pml)},
        )

    # ── Estimate from data proxies ──────────────────────────────────
    return _estimate_maturity(process_id, conn)


def _get_recent_survey(
    process_id: UUID,
    conn: psycopg.Connection,
) -> dict[str, Any] | None:
    """Get most recent maturity survey within 90 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT process_maturity_level, maturity_survey_date
               FROM process_competency_scores
               WHERE process_id = %s
                 AND maturity_survey_date IS NOT NULL
                 AND maturity_survey_date >= %s
               ORDER BY maturity_survey_date DESC
               LIMIT 1""",
            (str(process_id), cutoff),
        )
        return cur.fetchone()


def _estimate_maturity(
    process_id: UUID,
    conn: psycopg.Connection,
) -> DimensionScore:
    """Estimate PML from data proxies when no survey exists."""
    signals: dict[str, float] = {}

    with conn.cursor(row_factory=dict_row) as cur:
        # Documentation proxy — do process_metrics rows reference docs?
        cur.execute(
            """SELECT COUNT(*) AS cnt
               FROM process_metrics
               WHERE process_id = %s
                 AND metric_date >= CURRENT_DATE - INTERVAL '90 days'""",
            (str(process_id),),
        )
        row = cur.fetchone()
        has_metrics = (row["cnt"] or 0) > 0

        # Standardization proxy — low variance in cycle times
        cur.execute(
            """SELECT STDDEV(avg_cycle_time_hours) AS ct_stddev,
                      AVG(avg_cycle_time_hours) AS ct_avg,
                      COUNT(*) AS cnt
               FROM process_metrics
               WHERE process_id = %s
                 AND avg_cycle_time_hours IS NOT NULL
                 AND metric_date >= CURRENT_DATE - INTERVAL '90 days'""",
            (str(process_id),),
        )
        ct_row = cur.fetchone()

        # Measurability — how many metric columns are non-null?
        cur.execute(
            """SELECT COUNT(*) AS total,
                      COUNT(velocity_vs_plan) AS has_velocity,
                      COUNT(error_rate) AS has_error,
                      COUNT(overdue_rate) AS has_overdue,
                      COUNT(avg_cycle_time_hours) AS has_ct,
                      COUNT(cost_per_unit) AS has_cost
               FROM process_metrics
               WHERE process_id = %s
                 AND metric_date >= CURRENT_DATE - INTERVAL '90 days'""",
            (str(process_id),),
        )
        meas_row = cur.fetchone()

    # Score sub-signals [0-1]
    # Documentation/measurement exists
    if has_metrics:
        signals["documented"] = 0.6
    else:
        signals["documented"] = 0.0

    # Standardization: low CV (coefficient of variation) = more standardized
    if ct_row and ct_row["ct_avg"] and ct_row["ct_avg"] > 0 and ct_row["cnt"] >= 4:
        cv = (ct_row["ct_stddev"] or 0) / ct_row["ct_avg"]
        # CV < 0.2 = highly standardized, CV > 1.0 = chaotic
        signals["standardized"] = max(0.0, min(1.0, 1.0 - cv))
    else:
        signals["standardized"] = 0.3

    # Measurability: how many metrics are tracked
    if meas_row and meas_row["total"] > 0:
        measured = sum(1 for k in ("has_velocity", "has_error", "has_overdue", "has_ct", "has_cost")
                       if (meas_row.get(k) or 0) > 0)
        signals["measurable"] = measured / 5.0
    else:
        signals["measurable"] = 0.0

    # Composite estimate
    raw = (
        0.30 * signals.get("documented", 0)
        + 0.40 * signals.get("standardized", 0)
        + 0.30 * signals.get("measurable", 0)
    )
    estimated_pml = max(1, min(5, round(1 + raw * 4)))
    final_score = round(1.0 + raw * 4.0, 2)

    log.debug(
        "d3_estimated",
        process_id=str(process_id),
        score=final_score,
        estimated_pml=estimated_pml,
    )

    return DimensionScore(
        name="maturity",
        score=final_score,
        confidence=0.3,
        evidence={
            "source": "estimated",
            "estimated_pml": estimated_pml,
            **{f"signal_{k}": round(v, 3) for k, v in signals.items()},
        },
        sub_scores=signals,
    )
