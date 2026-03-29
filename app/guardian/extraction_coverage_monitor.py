"""
Extraction Coverage Monitor — track chunks without events, alert on coverage drops.

Queries chunks that have no events and no negative check record,
compares against historical snapshots, alerts if coverage drops >5%.
"""
from __future__ import annotations

import structlog

from app.db.postgres import get_pg_connection
from app.guardian.alert_manager import AlertManager

log = structlog.get_logger("extraction_coverage_monitor")

alert_mgr = AlertManager()


def check_extraction_coverage() -> dict:
    """Check extraction coverage and alert if drop >5%.

    Returns: {
        total_chunks, covered_chunks, uncovered_chunks,
        coverage_pct, previous_coverage_pct, drop_pct,
        healthy, snapshot_saved
    }
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Total chunks
            cur.execute("SELECT COUNT(*) FROM chunks")
            total_chunks = cur.fetchone()[0]

            if total_chunks == 0:
                return {
                    "total_chunks": 0, "covered_chunks": 0, "uncovered_chunks": 0,
                    "coverage_pct": 100.0, "healthy": True, "snapshot_saved": False,
                }

            # Uncovered: chunks without events AND without negative check
            cur.execute("""
                SELECT COUNT(*) FROM chunks c
                LEFT JOIN events e ON e.chunk_id = c.id
                LEFT JOIN chunks_event_checked cec ON cec.chunk_id = c.id
                WHERE e.id IS NULL AND cec.chunk_id IS NULL
            """)
            uncovered_chunks = cur.fetchone()[0]

            covered_chunks = total_chunks - uncovered_chunks
            coverage_pct = round((covered_chunks / total_chunks) * 100, 2) if total_chunks > 0 else 100.0

            # Get previous snapshot
            cur.execute("""
                SELECT coverage_pct FROM extraction_coverage_snapshots
                ORDER BY created_at DESC LIMIT 1
            """)
            prev_row = cur.fetchone()
            previous_coverage_pct = float(prev_row[0]) if prev_row else None

            # Calculate drop
            drop_pct = 0.0
            if previous_coverage_pct is not None:
                drop_pct = round(previous_coverage_pct - coverage_pct, 2)

            # Save snapshot
            snapshot_saved = False
            try:
                cur.execute("""
                    INSERT INTO extraction_coverage_snapshots
                        (total_chunks, covered_chunks, uncovered_chunks, coverage_pct)
                    VALUES (%s, %s, %s, %s)
                """, (total_chunks, covered_chunks, uncovered_chunks, coverage_pct))
                conn.commit()
                snapshot_saved = True
            except Exception as e:
                log.warning("coverage_snapshot_save_failed", error=str(e))
                conn.rollback()

    healthy = drop_pct <= 5.0

    if not healthy:
        alert_mgr.send(
            tier=2,
            category="extraction_coverage",
            title="Extraction coverage drop detected",
            message=(
                f"Coverage dropped by {drop_pct}%: "
                f"{previous_coverage_pct}% -> {coverage_pct}% "
                f"({uncovered_chunks}/{total_chunks} uncovered)"
            ),
        )

    log.info("extraction_coverage_checked",
             total=total_chunks, covered=covered_chunks,
             coverage_pct=coverage_pct, drop_pct=drop_pct, healthy=healthy)

    return {
        "total_chunks": total_chunks,
        "covered_chunks": covered_chunks,
        "uncovered_chunks": uncovered_chunks,
        "coverage_pct": coverage_pct,
        "previous_coverage_pct": previous_coverage_pct,
        "drop_pct": drop_pct,
        "healthy": healthy,
        "snapshot_saved": snapshot_saved,
    }


if __name__ == "__main__":
    import json
    result = check_extraction_coverage()
    print(json.dumps(result, indent=2, default=str))
