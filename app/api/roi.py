"""ROI Monitoring API — builder/management/life/operational ROI tracking."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.analysis.roi.hierarchy import (
    get_hierarchy_tree,
    get_entity,
    create_entity,
    get_owner_entity,
)
from app.analysis.roi.activity_tracker import scan_and_record_activities
from app.analysis.roi.roi_reporter import get_roi_report, get_leaderboard
from app.db.postgres import get_pg_connection

router = APIRouter(prefix="/roi", tags=["roi"])


# ── Schemas ──────────────────────────────────────────────────────

class HierarchyCreate(BaseModel):
    name: str
    type: str = Field(pattern="^(owner|company|department|team|user)$")
    parent_id: int | None = None
    hourly_rate_pln: float = 0
    metadata: dict = Field(default_factory=dict)


class ActivityCreate(BaseModel):
    entity_id: int
    activity_type: str
    domain: str = Field(pattern="^(builder|management|life|operational)$")
    value_pln: float = 0
    time_saved_min: int = 0
    description: str | None = None


# ── Summary endpoints ────────────────────────────────────────────

@router.get("/summary")
def roi_summary(
    entity_id: int | None = None,
    period: str = Query(default="week", pattern="^(week|month|quarter)$"),
) -> dict[str, Any]:
    """ROI summary for an entity (defaults to owner/Sebastian)."""
    return get_roi_report(entity_id=entity_id, period=period)


@router.get("/builder")
def roi_builder(
    period: str = Query(default="week", pattern="^(week|month|quarter)$"),
) -> dict[str, Any]:
    """Builder ROI — system development value."""
    owner = get_owner_entity()
    if not owner:
        raise HTTPException(404, "No owner entity found")
    return get_roi_report(entity_id=owner["id"], domain="builder", period=period)


@router.get("/management")
def roi_management(
    period: str = Query(default="week", pattern="^(week|month|quarter)$"),
) -> dict[str, Any]:
    """Management ROI — delegation and decision value."""
    owner = get_owner_entity()
    if not owner:
        raise HTTPException(404, "No owner entity found")
    return get_roi_report(entity_id=owner["id"], domain="management", period=period)


@router.get("/life")
def roi_life(
    period: str = Query(default="week", pattern="^(week|month|quarter)$"),
) -> dict[str, Any]:
    """Life ROI — personal affairs assisted."""
    owner = get_owner_entity()
    if not owner:
        raise HTTPException(404, "No owner entity found")
    return get_roi_report(entity_id=owner["id"], domain="life", period=period)


@router.get("/company/{company_id}")
def roi_company(
    company_id: int,
    period: str = Query(default="month", pattern="^(week|month|quarter)$"),
) -> dict[str, Any]:
    """Company-level ROI aggregation."""
    entity = get_entity(company_id)
    if not entity:
        raise HTTPException(404, f"Entity {company_id} not found")
    return get_roi_report(entity_id=company_id, period=period)


@router.get("/leaderboard")
def roi_leaderboard(
    period: str = Query(default="week", pattern="^(week|month)$"),
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Rank entities by ROI value."""
    return get_leaderboard(period=period, limit=limit)


# ── Activity endpoints ───────────────────────────────────────────

@router.post("/activity")
def log_activity(req: ActivityCreate) -> dict[str, Any]:
    """Manually log a value-generating activity."""
    entity = get_entity(req.entity_id)
    if not entity:
        raise HTTPException(404, f"Entity {req.entity_id} not found")

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO roi_activities "
                "(entity_id, activity_type, domain, value_pln, time_saved_min, description) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, created_at",
                (req.entity_id, req.activity_type, req.domain,
                 req.value_pln, req.time_saved_min, req.description),
            )
            rows = cur.fetchall()
            conn.commit()

    if not rows:
        raise HTTPException(500, "Activity insert returned no ID")
    return {
        "id": rows[0][0],
        "created_at": str(rows[0][1]),
        "status": "recorded",
    }


@router.post("/scan")
def scan_activities(
    since: str | None = Query(default=None, description="ISO date to scan from"),
) -> dict[str, Any]:
    """Trigger activity auto-detection scan."""
    since_dt = None
    if since:
        since_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    return scan_and_record_activities(since=since_dt)


# ── Hierarchy endpoints ──────────────────────────────────────────

@router.get("/hierarchy")
def list_hierarchy() -> list[dict[str, Any]]:
    """Get full organizational hierarchy."""
    return get_hierarchy_tree()


@router.post("/hierarchy")
def add_hierarchy_node(req: HierarchyCreate) -> dict[str, Any]:
    """Add a node to the hierarchy."""
    return create_entity(
        name=req.name,
        entity_type=req.type,
        parent_id=req.parent_id,
        hourly_rate_pln=req.hourly_rate_pln,
        metadata=req.metadata,
    )
