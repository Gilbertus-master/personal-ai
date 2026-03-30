"""
GET /ingestion/dashboard — full ingestion health overview.

Combines source freshness, extraction backlogs, DLQ stats, and guardian alerts
into a single dashboard response.
"""
import subprocess
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter

from app.db.postgres import get_pg_connection

router = APIRouter(tags=["ingestion"])
log = structlog.get_logger()

SLA_THRESHOLDS = {
    "email": 2,
    "teams": 2,
    "calendar": 4,
    "whatsapp_live": 4,
    "audio_transcript": 8,
    "document": 24,
    "whatsapp": 24,
    "spreadsheet": 168,
}


def _get_source_health(conn) -> list[dict]:
    """Per-source health with freshness, trend, DLQ, circuit breaker."""
    sources = []
    with conn.cursor() as cur:
        # Source freshness from sources table
        cur.execute("""
            SELECT source_type,
                   MAX(imported_at) as last_import,
                   EXTRACT(EPOCH FROM NOW() - MAX(imported_at))/3600 as hours_stale
            FROM sources
            GROUP BY source_type
        """)
        freshness = {row[0]: {"last_import": row[1], "hours_stale": float(row[2]) if row[2] else 0.0}
                     for row in cur.fetchall()}

        # Latest ingestion_health metrics (today or most recent)
        cur.execute("""
            SELECT DISTINCT ON (source_type)
                   source_type, docs_24h, docs_7d_avg, status, trend, note
            FROM ingestion_health
            ORDER BY source_type, check_date DESC
        """)
        health_rows = {row[0]: {
            "docs_24h": row[1], "docs_7d_avg": float(row[2]) if row[2] else 0.0,
            "status": row[3], "trend": row[4] or "stable", "note": row[5],
        } for row in cur.fetchall()}

        # DLQ pending per source
        cur.execute("""
            SELECT source_type, COUNT(*) as cnt
            FROM ingestion_dlq
            WHERE status IN ('pending', 'retrying')
            GROUP BY source_type
        """)
        dlq_counts = {row[0]: row[1] for row in cur.fetchall()}

        # Circuit breaker states (table may not exist yet)
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'circuit_breakers'
            )
        """)
        breaker_states = {}
        rows = cur.fetchall()
        if rows and rows[0][0]:
            cur.execute("""
                SELECT source_type, state
                FROM circuit_breakers
                WHERE state != 'closed'
            """)
            breaker_states = {row[0]: row[1] for row in cur.fetchall()}

        # Last errors per source from DLQ
        cur.execute("""
            SELECT DISTINCT ON (source_type)
                   source_type, error_message
            FROM ingestion_dlq
            WHERE error_message IS NOT NULL
            ORDER BY source_type, created_at DESC
        """)
        last_errors = {row[0]: row[1][:200] if row[1] else None for row in cur.fetchall()}

    for source_type, sla in SLA_THRESHOLDS.items():
        fresh = freshness.get(source_type, {})
        health = health_rows.get(source_type, {})
        hours_stale = round(fresh.get("hours_stale", 0.0), 1)

        # Determine status from health table or compute from staleness
        if health.get("status"):
            status = health["status"]
        else:
            ratio = hours_stale / sla if sla > 0 else 0.0
            if ratio <= 0.5:
                status = "ok"
            elif ratio <= 1.0:
                status = "warning"
            elif ratio <= 3.0:
                status = "critical"
            else:
                status = "dead"

        last_import = fresh.get("last_import")

        sources.append({
            "source_type": source_type,
            "status": status,
            "last_import": last_import.isoformat() if last_import else None,
            "hours_stale": hours_stale,
            "sla_hours": sla,
            "docs_24h": health.get("docs_24h", 0),
            "docs_7d_avg": health.get("docs_7d_avg", 0.0),
            "trend": health.get("trend", "stable"),
            "circuit_breaker": breaker_states.get(source_type, "closed"),
            "dlq_pending": dlq_counts.get(source_type, 0),
            "last_error": last_errors.get(source_type),
        })

    sources.sort(key=lambda x: {"dead": 4, "critical": 3, "warning": 2, "ok": 1}.get(x["status"], 0), reverse=True)
    return sources


def _get_extraction_backlogs(conn) -> dict:
    """Entity, event, and embedding backlogs."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM chunks c
                 LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
                 LEFT JOIN chunks_entity_checked cec ON cec.chunk_id = c.id
                 WHERE ce.id IS NULL AND cec.chunk_id IS NULL) as entity_backlog,
                (SELECT COUNT(*) FROM chunks c
                 LEFT JOIN events e ON e.chunk_id = c.id
                 LEFT JOIN chunks_event_checked cec ON cec.chunk_id = c.id
                 WHERE e.id IS NULL AND cec.chunk_id IS NULL) as event_backlog,
                (SELECT COUNT(*) FROM chunks
                 WHERE (embedding_id IS NULL OR embedding_id = '')
                   AND embedding_status = 'pending') as embedding_backlog
        """)
        row = cur.fetchone()

    # Count running workers
    try:
        result = subprocess.run(
            ["bash", "-c", "ps aux | grep -E 'extraction\\.(entities|events)' | grep -v grep | wc -l"],
            capture_output=True, text=True, timeout=5)
        workers = int(result.stdout.strip())
    except Exception:
        workers = 0

    return {
        "entity_backlog": row[0] if row else 0,
        "event_backlog": row[1] if row else 0,
        "embedding_backlog": row[2] if row else 0,
        "workers_running": workers,
    }


def _get_alert_stats(conn) -> dict:
    """Unacknowledged critical alerts and recent auto-fixes."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE tier = 3 AND acknowledged = FALSE) as unacknowledged_critical,
                COUNT(*) FILTER (WHERE tier = 1 AND created_at > NOW() - INTERVAL '24 hours') as recent_auto_fixes
            FROM guardian_alerts
        """)
        row = cur.fetchone()

    return {
        "unacknowledged_critical": row[0] if row else 0,
        "recent_auto_fixes": row[1] if row else 0,
    }


@router.get("/ingestion/dashboard")
def ingestion_dashboard() -> dict:
    """Full ingestion health dashboard."""
    with get_pg_connection() as conn:
        try:
            sources = _get_source_health(conn)
        except Exception as e:
            log.error("ingestion_dashboard_sources_error", error=str(e))
            sources = []

        try:
            extraction = _get_extraction_backlogs(conn)
        except Exception as e:
            log.error("ingestion_dashboard_extraction_error", error=str(e))
            extraction = {"entity_backlog": 0, "event_backlog": 0, "embedding_backlog": 0, "workers_running": 0}

        try:
            alerts = _get_alert_stats(conn)
        except Exception as e:
            log.error("ingestion_dashboard_alerts_error", error=str(e))
            alerts = {"unacknowledged_critical": 0, "recent_auto_fixes": 0}

    # Overall health = worst source status
    status_order = {"dead": 4, "critical": 3, "warning": 2, "ok": 1}
    worst = max((status_order.get(s["status"], 0) for s in sources), default=1)
    overall = {4: "critical", 3: "critical", 2: "warning", 1: "ok"}.get(worst, "ok")

    return {
        "sources": sources,
        "extraction": extraction,
        "alerts": alerts,
        "overall_health": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
