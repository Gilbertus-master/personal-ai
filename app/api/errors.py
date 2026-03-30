"""Multi-user error reporting API — browser errors → DB → autofix pipeline."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.postgres import get_pg_connection

router = APIRouter(tags=["errors"])
log = structlog.get_logger(__name__)


class ErrorReport(BaseModel):
    user_id: str = "unknown"
    route: str | None = None
    error_type: str  # 'runtime', 'network', 'render', 'api'
    error_message: str
    error_stack: str | None = None
    component: str | None = None
    module: str | None = None
    browser: str | None = None
    user_agent: str | None = None
    app_version: str = "0.1"


@router.post("/errors/report")
async def report_error(payload: ErrorReport) -> dict:
    """Accept errors from user browsers."""
    with get_pg_connection() as conn:
        row = conn.execute(
            """INSERT INTO app_errors
               (user_id, route, error_type, error_message, error_stack,
                component, module, browser, user_agent, app_version)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                payload.user_id, payload.route, payload.error_type,
                payload.error_message, payload.error_stack,
                payload.component, payload.module,
                payload.browser, payload.user_agent, payload.app_version,
            ),
        ).fetchone()
        conn.commit()
    error_id = row[0] if row else None
    log.info("error_reported", error_id=error_id, error_type=payload.error_type,
             route=payload.route, component=payload.component)
    return {"status": "logged", "error_id": error_id}


@router.get("/errors/unresolved")
async def get_unresolved_errors(limit: int = 50) -> dict:
    """Return unresolved errors for the autofix monitor."""
    with get_pg_connection() as conn:
        rows = conn.execute(
            """SELECT id, user_id, route, error_type, error_message, error_stack,
                      component, module, browser, app_version, created_at
               FROM app_errors
               WHERE resolved = FALSE
               ORDER BY created_at DESC
               LIMIT %s""",
            (limit,),
        ).fetchall()
    errors = [
        {
            "id": r[0], "user_id": r[1], "route": r[2], "error_type": r[3],
            "error_message": r[4], "error_stack": r[5], "component": r[6],
            "module": r[7], "browser": r[8], "app_version": r[9],
            "created_at": r[10].isoformat() if r[10] else None,
        }
        for r in rows
    ]
    return {"errors": errors, "count": len(errors)}


@router.post("/errors/{error_id}/resolve")
async def resolve_error(error_id: int, fix_commit: str | None = None) -> dict:
    """Mark an error as resolved after autofix or manual fix."""
    with get_pg_connection() as conn:
        result = conn.execute(
            """UPDATE app_errors
               SET resolved = TRUE, fix_commit = %s
               WHERE id = %s AND resolved = FALSE
               RETURNING id""",
            (fix_commit, error_id),
        ).fetchone()
        conn.commit()
    if not result:
        raise HTTPException(status_code=404, detail="Error not found or already resolved")
    log.info("error_resolved", error_id=error_id, fix_commit=fix_commit)
    return {"status": "resolved", "error_id": error_id}
