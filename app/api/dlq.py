"""DLQ (Dead Letter Queue) API endpoints for monitoring and retrying failed imports."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db.postgres import get_pg_connection

router = APIRouter(prefix="/dlq", tags=["dlq"])


@router.get("")
def list_dlq(
    status: str | None = None,
    source_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List DLQ items with optional filters."""
    conditions = []
    params: list = []

    if status:
        conditions.append("status = %s")
        params.append(status)
    if source_type:
        conditions.append("source_type = %s")
        params.append(source_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, source_type, source_name, raw_path, title,
                       error_message, error_type, retry_count, max_retries,
                       status, created_at::text, last_retry_at::text, resolved_at::text
                FROM ingestion_dlq
                {where}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

            cur.execute(f"SELECT COUNT(*) FROM ingestion_dlq {where}", params)
            total = cur.fetchall()[0][0]

    return {"items": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/stats")
def dlq_stats():
    """Summary stats per source_type and status."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_type, status, COUNT(*),
                       MIN(created_at)::text AS oldest,
                       MAX(created_at)::text AS newest
                FROM ingestion_dlq
                GROUP BY source_type, status
                ORDER BY source_type, status
                """
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                       COUNT(*) FILTER (WHERE status = 'retrying') AS retrying,
                       COUNT(*) FILTER (WHERE status = 'resolved') AS resolved,
                       COUNT(*) FILTER (WHERE status = 'abandoned') AS abandoned,
                       COUNT(*) AS total
                FROM ingestion_dlq
                """
            )
            summary_row = cur.fetchone()

    return {
        "summary": {
            "pending": summary_row[0],
            "retrying": summary_row[1],
            "resolved": summary_row[2],
            "abandoned": summary_row[3],
            "total": summary_row[4],
        },
        "by_source": rows,
    }


@router.post("/{dlq_id}/retry")
def retry_one(dlq_id: int):
    """Manually retry a single DLQ item."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status FROM ingestion_dlq WHERE id = %s",
                (dlq_id,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="DLQ item not found")
    if row[1] == "resolved":
        return {"status": "already_resolved", "id": dlq_id}

    from app.guardian.dlq_worker import mark_retrying, mark_resolved, mark_failed, retry_item

    # Fetch the full item
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_type, source_name, raw_path, title,
                       error_message, error_type, payload, retry_count, max_retries
                FROM ingestion_dlq WHERE id = %s
                """,
                (dlq_id,),
            )
            cols = [d[0] for d in cur.description]
            item = dict(zip(cols, cur.fetchone()))

    mark_retrying(dlq_id)

    try:
        success = retry_item(item)
        if success:
            mark_resolved(dlq_id)
            return {"status": "resolved", "id": dlq_id}
        else:
            mark_failed(dlq_id, "Manual retry returned False")
            return {"status": "failed", "id": dlq_id}
    except Exception as e:
        mark_failed(dlq_id, str(e))
        raise HTTPException(status_code=500, detail=f"Retry failed: {e}")


@router.post("/retry-all")
def retry_all():
    """Retry all pending DLQ items."""
    from app.guardian.dlq_worker import run_worker
    stats = run_worker()
    return {"status": "done", **stats}
