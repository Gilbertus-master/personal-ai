"""Alert resolution API — resolve (fix/suppress), manage fix tasks and suppressions."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.postgres import get_pg_connection

router = APIRouter(tags=["alerts"])
log = structlog.get_logger(__name__)


# ── Schemas ──────────────────────────────────────────────────────

class ResolveRequest(BaseModel):
    action: str  # "fix" | "suppress"
    comment: str = ""
    fix_instruction: str | None = None


class ResolveResponse(BaseModel):
    status: str
    action: str
    task_id: int | None = None


class SuppressionItem(BaseModel):
    id: int
    alert_type: str
    source_type: str | None
    reason: str | None
    created_by: str | None
    created_at: str | None


class FixTaskItem(BaseModel):
    id: int
    alert_id: int | None
    title: str
    instruction: str
    comment: str | None
    status: str
    result: str | None
    created_at: str | None
    updated_at: str | None


class CompleteTaskRequest(BaseModel):
    result: str = ""


# ── Helpers ──────────────────────────────────────────────────────

def is_suppressed(alert_type: str, source_type: str | None = None) -> bool:
    """Check if an alert type is suppressed."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM alert_suppressions
                WHERE alert_type = %s
                  AND (source_type IS NULL OR source_type = %s)
                LIMIT 1
                """,
                (alert_type, source_type),
            )
            return cur.fetchone() is not None


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/alerts/{alert_id}/resolve", response_model=ResolveResponse)
def resolve_alert(alert_id: int, req: ResolveRequest):
    """Resolve an alert: either create a fix task or suppress future similar alerts."""
    if req.action not in ("fix", "suppress"):
        raise HTTPException(status_code=400, detail="action must be 'fix' or 'suppress'")

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Verify alert exists
            cur.execute(
                "SELECT id, alert_type, title, description FROM alerts WHERE id = %s",
                (alert_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Alert not found")

            alert_type = row[1]
            alert_title = row[2]
            alert_desc = row[3]

            # Mark alert as inactive (acknowledged)
            cur.execute(
                "UPDATE alerts SET is_active = FALSE WHERE id = %s",
                (alert_id,),
            )

            task_id = None

            if req.action == "fix":
                instruction = req.fix_instruction or alert_desc or ""
                cur.execute(
                    """
                    INSERT INTO alert_fix_tasks (alert_id, title, instruction, comment)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (alert_id, alert_title, instruction, req.comment),
                )
                task_id = cur.fetchone()[0]
                log.info("alert_fix_task_created", alert_id=alert_id, task_id=task_id)

            elif req.action == "suppress":
                cur.execute(
                    """
                    INSERT INTO alert_suppressions (alert_type, reason)
                    VALUES (%s, %s)
                    ON CONFLICT (alert_type, COALESCE(source_type, '__null__'))
                    DO UPDATE SET reason = EXCLUDED.reason
                    RETURNING id
                    """,
                    (alert_type, req.comment),
                )
                suppression_id = cur.fetchone()[0]
                log.info("alert_suppressed", alert_type=alert_type, suppression_id=suppression_id)

            conn.commit()

    return ResolveResponse(status="resolved", action=req.action, task_id=task_id)


@router.get("/alerts/suppressions")
def list_suppressions():
    """List active alert suppression rules."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, alert_type, source_type, reason, created_by, created_at
                FROM alert_suppressions
                ORDER BY created_at DESC
                """
            )
            cols = [d[0] for d in cur.description]
            rows = [
                {**dict(zip(cols, row)), "created_at": row[5].isoformat() if row[5] else None}
                for row in cur.fetchall()
            ]
    return {"suppressions": rows}


@router.delete("/alerts/suppressions/{suppression_id}")
def delete_suppression(suppression_id: int):
    """Remove a suppression rule — re-enables alerts of that type."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM alert_suppressions WHERE id = %s RETURNING id",
                (suppression_id,),
            )
            deleted = cur.fetchone()
            if not deleted:
                raise HTTPException(status_code=404, detail="Suppression not found")
            conn.commit()
    log.info("suppression_deleted", id=suppression_id)
    return {"status": "deleted", "id": suppression_id}


@router.get("/alerts/fix-tasks")
def list_fix_tasks(status: str | None = Query(default=None)):
    """List alert fix tasks, optionally filtered by status."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    """
                    SELECT id, alert_id, title, instruction, comment, status, result,
                           created_at, updated_at
                    FROM alert_fix_tasks
                    WHERE status = %s
                    ORDER BY created_at DESC
                    """,
                    (status,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, alert_id, title, instruction, comment, status, result,
                           created_at, updated_at
                    FROM alert_fix_tasks
                    ORDER BY
                        CASE status WHEN 'pending' THEN 1 WHEN 'in_progress' THEN 2
                                    WHEN 'failed' THEN 3 ELSE 4 END,
                        created_at DESC
                    """
                )
            cols = [d[0] for d in cur.description]
            rows = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                d["created_at"] = row[7].isoformat() if row[7] else None
                d["updated_at"] = row[8].isoformat() if row[8] else None
                rows.append(d)
    return {"tasks": rows}


@router.post("/alerts/fix-tasks/{task_id}/complete")
def complete_fix_task(task_id: int, req: CompleteTaskRequest):
    """Mark a fix task as done with result."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE alert_fix_tasks
                SET status = 'done', result = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING id
                """,
                (req.result, task_id),
            )
            updated = cur.fetchone()
            if not updated:
                raise HTTPException(status_code=404, detail="Fix task not found")
            conn.commit()
    log.info("fix_task_completed", task_id=task_id)
    return {"status": "completed", "task_id": task_id}
