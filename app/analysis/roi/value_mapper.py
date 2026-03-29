"""ROI Value Mapper — converts activities to PLN values based on configurable rates."""
from __future__ import annotations

import os

import structlog
from dotenv import load_dotenv

load_dotenv()
log = structlog.get_logger(__name__)

# Configurable rates (PLN per hour)
RATE_OWNER = float(os.getenv("ROI_RATE_OWNER_PLN", "600"))
RATE_SENIOR = float(os.getenv("ROI_RATE_SENIOR_PLN", "300"))
RATE_EMPLOYEE = float(os.getenv("ROI_RATE_EMPLOYEE_PLN", "150"))

# Default time saved per activity (minutes)
DEFAULT_QUERY_MIN = int(os.getenv("ROI_DEFAULT_QUERY_MINUTES", "30"))
DEFAULT_DECISION_MIN = int(os.getenv("ROI_DEFAULT_DECISION_MINUTES", "60"))
DEFAULT_ACTION_MIN = int(os.getenv("ROI_DEFAULT_ACTION_MINUTES", "45"))
DEFAULT_COMMUNICATION_MIN = int(os.getenv("ROI_DEFAULT_COMMUNICATION_MINUTES", "20"))
DEFAULT_DOCUMENT_MIN = int(os.getenv("ROI_DEFAULT_DOCUMENT_MINUTES", "15"))
DEFAULT_CODE_FIX_MIN = int(os.getenv("ROI_DEFAULT_CODE_FIX_MINUTES", "60"))

# Severity multipliers for code fixes
CODE_FIX_SEVERITY = {
    "critical": 4.0,
    "high": 2.0,
    "medium": 1.0,
    "low": 0.5,
}

# Activity type → (default_minutes, domain)
ACTIVITY_DEFAULTS: dict[str, tuple[int, str]] = {
    "query_answered": (DEFAULT_QUERY_MIN, "operational"),
    "decision_made": (DEFAULT_DECISION_MIN, "management"),
    "action_executed": (DEFAULT_ACTION_MIN, "management"),
    "code_fix": (DEFAULT_CODE_FIX_MIN, "builder"),
    "knowledge_added": (DEFAULT_DOCUMENT_MIN, "builder"),
    "meeting_productive": (30, "management"),
    "communication_sent": (DEFAULT_COMMUNICATION_MIN, "management"),
}


def get_rate_for_entity(entity: dict) -> float:
    """Get hourly rate for an entity, falling back to type-based defaults."""
    if entity.get("hourly_rate_pln") and float(entity["hourly_rate_pln"]) > 0:
        return float(entity["hourly_rate_pln"])
    entity_type = entity.get("type", "user")
    if entity_type == "owner":
        return RATE_OWNER
    if entity_type in ("company", "department"):
        return RATE_SENIOR
    return RATE_EMPLOYEE


def map_activity_value(
    activity_type: str,
    entity: dict,
    severity: str | None = None,
    meeting_roi_score: float | None = None,
    custom_minutes: int | None = None,
) -> tuple[float, int]:
    """
    Map an activity to (value_pln, time_saved_min).

    Returns:
        (value_pln, time_saved_min)
    """
    rate = get_rate_for_entity(entity)
    defaults = ACTIVITY_DEFAULTS.get(activity_type, (DEFAULT_QUERY_MIN, "operational"))
    base_minutes = custom_minutes if custom_minutes is not None else defaults[0]

    # Severity multiplier for code fixes
    if activity_type == "code_fix" and severity:
        multiplier = CODE_FIX_SEVERITY.get(severity.lower(), 1.0)
        base_minutes = int(base_minutes * multiplier)

    # Meeting ROI score scaling
    if activity_type == "meeting_productive" and meeting_roi_score is not None:
        base_minutes = int(base_minutes * (meeting_roi_score / 5.0))

    value_pln = round(rate * (base_minutes / 60.0), 2)

    log.debug(
        "roi_value_mapped",
        activity_type=activity_type,
        rate=rate,
        minutes=base_minutes,
        value_pln=value_pln,
    )

    return value_pln, base_minutes


def get_domain_for_activity(activity_type: str, entity: dict) -> str:
    """Determine ROI domain based on activity type and entity."""
    defaults = ACTIVITY_DEFAULTS.get(activity_type)
    if defaults:
        # Owner's queries are builder, not operational
        if activity_type == "query_answered" and entity.get("type") == "owner":
            return "builder"
        return defaults[1]
    return "operational"
