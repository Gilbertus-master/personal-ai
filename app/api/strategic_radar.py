"""Strategic Radar API — cross-domain strategic intelligence endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.analysis.strategic_radar import run_full_radar, get_radar_history

router = APIRouter(prefix="/strategic-radar", tags=["strategic-radar"])


@router.get("")
async def strategic_radar():
    """Run full strategic radar: collect signals, detect patterns, generate recommendations."""
    result = run_full_radar()
    return result


@router.get("/history")
async def strategic_radar_history(
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
):
    """Get historical radar snapshots for the last N days."""
    snapshots = get_radar_history(days=days)
    return {"snapshots": snapshots, "count": len(snapshots)}
