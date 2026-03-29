"""Guardian Alert API — list, acknowledge, and manage three-tier alerts."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.guardian.alert_manager import AlertManager

router = APIRouter(prefix="/alerts/guardian", tags=["guardian-alerts"])

_mgr = AlertManager()


@router.get("")
def list_alerts(tier: int | None = None, limit: int = 20):
    """List recent guardian alerts, optionally filtered by tier."""
    return {"alerts": _mgr.get_active(tier=tier, limit=limit)}


@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int):
    """Acknowledge a single alert — stops critical repeat."""
    ok = _mgr.acknowledge(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")
    return {"status": "acknowledged", "alert_id": alert_id}


class AckAllRequest(BaseModel):
    category: str | None = None


@router.post("/acknowledge-all")
def acknowledge_all(req: AckAllRequest | None = None):
    """Acknowledge all unacknowledged critical alerts."""
    category = req.category if req else None
    count = _mgr.acknowledge_latest(category=category)
    return {"status": "acknowledged", "count": count}


@router.get("/stats")
def alert_stats():
    """Summary counts by tier and acknowledgment status."""
    from app.db.postgres import get_pg_connection

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tier,
                       COUNT(*) FILTER (WHERE acknowledged = FALSE) AS open,
                       COUNT(*) FILTER (WHERE acknowledged = TRUE) AS acked,
                       COUNT(*) AS total
                FROM guardian_alerts
                WHERE created_at > NOW() - INTERVAL '7 days'
                GROUP BY tier
                ORDER BY tier
                """
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    return {"stats": rows}
