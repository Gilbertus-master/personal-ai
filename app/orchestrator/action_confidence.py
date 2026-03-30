"""
Action Confidence Scoring — determines auto-execute eligibility for action proposals.

Authority levels:
  0 = auto-execute immediately (e.g. internal logging, ticket creation)
  1 = notify + auto-execute after delay (e.g. reminder WhatsApp)
  2 = propose + wait for approval (e.g. send email to external)
  3 = propose only, never auto-execute (e.g. financial decisions)

Confidence scoring considers:
  - Signal type reliability
  - Historical approval rate for similar actions
  - Recipient sensitivity
  - Action reversibility
"""
from __future__ import annotations

import structlog
from typing import Any

from app.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

# Signal type base confidence scores (0.0 - 1.0)
SIGNAL_CONFIDENCE_MAP: dict[str, float] = {
    "market_insight": 0.7,
    "competitor_signal": 0.6,
    "goal_at_risk": 0.8,
    "overdue_commitment": 0.9,
    "calendar_conflict": 0.85,
    "communication_anomaly": 0.5,
    "predictive_alert": 0.4,
    "compliance_deadline": 0.95,
}

# Action type → base authority level
ACTION_AUTHORITY_MAP: dict[str, int] = {
    "create_ticket": 0,
    "send_whatsapp": 1,
    "send_email": 2,
    "schedule_meeting": 2,
    "omnius_command": 1,
    "financial_decision": 3,
    "contract_action": 3,
    "delegation": 2,
}

# Recipients that require higher authority
SENSITIVE_RECIPIENTS: set[str] = {
    "external", "client", "regulator", "board", "investor",
}


# ================================================================
# Schema
# ================================================================

def _ensure_tables() -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS action_confidence_log (
                    id BIGSERIAL PRIMARY KEY,
                    action_id BIGINT,
                    signal_type TEXT,
                    confidence NUMERIC(4,3) NOT NULL,
                    authority_level INTEGER NOT NULL DEFAULT 2,
                    reasoning TEXT,
                    approved BOOLEAN,
                    executed BOOLEAN,
                    outcome TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_confidence_log_action
                    ON action_confidence_log(action_id);
                CREATE INDEX IF NOT EXISTS idx_confidence_log_signal
                    ON action_confidence_log(signal_type);
            """)
        conn.commit()
    log.info("action_confidence.tables_ensured")


# ================================================================
# Confidence scoring
# ================================================================

def score_signal_confidence(
    signal_type: str,
    signal_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Score the confidence of a signal for action proposal.

    Returns:
        {confidence: float, authority_level: int, reasoning: str}
    """
    base_confidence = SIGNAL_CONFIDENCE_MAP.get(signal_type, 0.5)

    adjustments = []
    adjusted = base_confidence

    # Adjust by relevance score if present
    relevance = signal_data.get("relevance_score") or signal_data.get("relevance")
    if relevance is not None:
        relevance_factor = int(relevance) / 100.0
        adjusted = adjusted * 0.6 + relevance_factor * 0.4
        adjustments.append(f"relevance={relevance} -> factor {relevance_factor:.2f}")

    # Adjust by severity if present
    severity = signal_data.get("severity")
    if severity == "high":
        adjusted = min(adjusted + 0.1, 1.0)
        adjustments.append("severity=high +0.1")
    elif severity == "low":
        adjusted = max(adjusted - 0.1, 0.0)
        adjustments.append("severity=low -0.1")

    # Historical approval rate for this signal type
    try:
        hist_rate = _get_historical_approval_rate(signal_type)
        if hist_rate is not None:
            adjusted = adjusted * 0.7 + hist_rate * 0.3
            adjustments.append(f"historical_approval_rate={hist_rate:.2f}")
    except Exception:
        pass

    # Determine authority level
    action_type = signal_data.get("action_type", "create_ticket")
    recipient = signal_data.get("recipient", "")
    authority = determine_authority_level(action_type, adjusted, recipient)

    reasoning_parts = [
        f"base={base_confidence:.2f} ({signal_type})",
    ]
    if adjustments:
        reasoning_parts.append(f"adjustments: {', '.join(adjustments)}")
    reasoning_parts.append(f"final={adjusted:.3f}, authority_level={authority}")

    return {
        "confidence": round(adjusted, 3),
        "authority_level": authority,
        "reasoning": "; ".join(reasoning_parts),
    }


def determine_authority_level(
    action_type: str,
    confidence: float,
    recipient: str = "",
) -> int:
    """
    Determine the authority level required for an action.

    Returns: 0 (auto) to 3 (manual only)
    """
    base_authority = ACTION_AUTHORITY_MAP.get(action_type, 2)

    # Sensitive recipient bumps authority up
    recipient_lower = recipient.lower() if recipient else ""
    for sensitive in SENSITIVE_RECIPIENTS:
        if sensitive in recipient_lower:
            base_authority = max(base_authority, 2)
            break

    # High confidence can lower authority (but never below action's base - 1)
    if confidence >= 0.9 and base_authority > 0:
        base_authority = max(base_authority - 1, 0)
    elif confidence < 0.5:
        base_authority = min(base_authority + 1, 3)

    return base_authority


def _get_historical_approval_rate(signal_type: str) -> float | None:
    """Get approval rate for actions from this signal type (last 90 days)."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE approved = TRUE) as approved_count,
                        COUNT(*) as total_count
                    FROM action_confidence_log
                    WHERE signal_type = %s
                      AND created_at > NOW() - INTERVAL '90 days'
                      AND approved IS NOT NULL
                """, (signal_type,))
                row = cur.fetchone()
                if row and row[1] >= 5:  # need at least 5 data points
                    return row[0] / row[1]
                return None
    except Exception:
        return None


# ================================================================
# Feedback recording
# ================================================================

def record_feedback(
    action_id: int,
    approved: bool,
    executed: bool = False,
    outcome: str | None = None,
    signal_type: str | None = None,
    confidence: float | None = None,
    authority_level: int | None = None,
    reasoning: str | None = None,
) -> dict[str, Any]:
    """Record feedback for a confidence-scored action."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO action_confidence_log
                   (action_id, signal_type, confidence, authority_level,
                    reasoning, approved, executed, outcome)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    action_id,
                    signal_type,
                    confidence or 0.0,
                    authority_level or 2,
                    reasoning,
                    approved,
                    executed,
                    outcome,
                ),
            )
            log_id = cur.fetchall()[0][0]
        conn.commit()

    log.info("action_confidence.feedback_recorded",
             log_id=log_id, action_id=action_id, approved=approved, executed=executed)

    return {
        "log_id": log_id,
        "action_id": action_id,
        "approved": approved,
        "executed": executed,
    }


def get_confidence_stats(days: int = 30) -> dict[str, Any]:
    """Get confidence scoring stats for dashboard."""
    _ensure_tables()

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    signal_type,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE approved = TRUE) as approved,
                    COUNT(*) FILTER (WHERE executed = TRUE) as executed,
                    AVG(confidence) as avg_confidence
                FROM action_confidence_log
                WHERE created_at > NOW() - (%s || ' days')::interval
                GROUP BY signal_type
                ORDER BY total DESC
            """, (str(days),))

            by_signal = [
                {
                    "signal_type": r[0],
                    "total": r[1],
                    "approved": r[2],
                    "executed": r[3],
                    "approval_rate": round(r[2] / r[1], 2) if r[1] > 0 else 0,
                    "avg_confidence": round(float(r[4]), 3) if r[4] else 0,
                }
                for r in cur.fetchall()
            ]

            cur.execute("""
                SELECT
                    authority_level,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE approved = TRUE) as approved
                FROM action_confidence_log
                WHERE created_at > NOW() - (%s || ' days')::interval
                GROUP BY authority_level
                ORDER BY authority_level
            """, (str(days),))

            by_authority = [
                {
                    "authority_level": r[0],
                    "total": r[1],
                    "approved": r[2],
                    "approval_rate": round(r[2] / r[1], 2) if r[1] > 0 else 0,
                }
                for r in cur.fetchall()
            ]

    return {
        "by_signal_type": by_signal,
        "by_authority_level": by_authority,
        "period_days": days,
    }
