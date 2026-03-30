"""
Data Quality Calibrator — automated detection and fixing of data quality issues.

Detects and auto-fixes:
1. Events without timestamps (backfill from chunk/document)
2. Chunks without timestamps (backfill from document)
3. Orphan documents (no chunks — parsing failures)
4. Stale data sources (alerts + triggers re-sync)
5. Extraction coverage gaps
6. Duplicate entities
7. Low-confidence events

Cron: daily at 5:30 CET (4:30 UTC), before morning brief.
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

import json
from datetime import datetime, timezone
from typing import Any

from app.db.postgres import get_pg_connection

# Staleness thresholds per source (hours)
SOURCE_STALENESS_HOURS = {
    "email": 4,
    "teams": 2,
    "whatsapp_live": 12,  # may be inactive overnight
    "calendar": 24,
    "audio_transcript": 48,
    "claude_code_full": 2,
    "email_attachment": 8,
    "document": 168,  # weekly is OK
    "spreadsheet": 336,  # bi-weekly
    "chatgpt": 720,  # disabled, monthly threshold
    "whatsapp": 168,  # historical import
}


def run_calibration() -> dict[str, Any]:
    """Run full data quality calibration. Returns report of issues found and fixed."""
    started = datetime.now(tz=timezone.utc)
    report = {
        "timestamp": started.isoformat(),
        "fixes": {},
        "issues": [],
        "warnings": [],
    }

    # Fix 1: Chunks without timestamps
    fix1 = _fix_chunk_timestamps()
    report["fixes"]["chunk_timestamps_backfilled"] = fix1

    # Fix 2: Events without timestamps
    fix2 = _fix_event_timestamps()
    report["fixes"]["event_timestamps_backfilled"] = fix2

    # Fix 3: Orphan documents (no chunks)
    fix3 = _fix_orphan_documents()
    report["fixes"]["orphan_documents_cleaned"] = fix3

    # Check 4: Source staleness
    stale = _check_source_staleness()
    report["issues"].extend(stale)

    # Check 5: Extraction coverage
    coverage = _check_extraction_coverage()
    report["issues"].extend(coverage)

    # Fix 6: Duplicate entities
    fix6 = _fix_duplicate_entities()
    report["fixes"]["duplicate_entities_merged"] = fix6

    # Check 7: Low confidence events
    low_conf = _check_low_confidence()
    if low_conf:
        report["warnings"].append(low_conf)

    # Summary stats
    report["stats"] = _get_quality_stats()

    latency_ms = int((datetime.now(tz=timezone.utc) - started).total_seconds() * 1000)
    report["latency_ms"] = latency_ms

    total_fixes = sum(v for v in report["fixes"].values() if isinstance(v, int))
    total_issues = len(report["issues"])

    log.info("data_quality_calibration_done",
             fixes=total_fixes, issues=total_issues, latency_ms=latency_ms)

    # Send WhatsApp alert if critical issues found
    if total_issues > 0:
        _send_quality_alert(report)

    return report


# ---------------------------------------------------------------------------
# Auto-fix functions
# ---------------------------------------------------------------------------

def _fix_chunk_timestamps() -> int:
    """Backfill NULL chunk timestamps from document created_at."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE chunks c SET timestamp_start = d.created_at
                FROM documents d
                WHERE c.document_id = d.id
                AND c.timestamp_start IS NULL
                AND d.created_at IS NOT NULL
            """)
            count = cur.rowcount
            conn.commit()
    if count > 0:
        log.info("chunk_timestamps_fixed", count=count)
    return count


def _fix_event_timestamps() -> int:
    """Backfill NULL event_time from chunk timestamp_start or document created_at."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # First try chunk timestamp
            cur.execute("""
                UPDATE events e SET event_time = c.timestamp_start
                FROM chunks c
                WHERE e.chunk_id = c.id
                AND e.event_time IS NULL
                AND c.timestamp_start IS NOT NULL
            """)
            count1 = cur.rowcount

            # Then try document created_at for remaining
            cur.execute("""
                UPDATE events e SET event_time = d.created_at
                FROM documents d
                WHERE e.document_id = d.id
                AND e.event_time IS NULL
                AND d.created_at IS NOT NULL
            """)
            count2 = cur.rowcount

            conn.commit()

    total = count1 + count2
    if total > 0:
        log.info("event_timestamps_fixed", from_chunk=count1, from_document=count2)
    return total


def _fix_orphan_documents() -> int:
    """Remove documents that have no associated chunks (parsing failures)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Only clean docs older than 1 hour (give pipeline time to process)
            cur.execute("""
                DELETE FROM documents d
                WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.document_id = d.id)
                AND d.created_at < NOW() - INTERVAL '1 hour'
            """)
            count = cur.rowcount
            conn.commit()
    if count > 0:
        log.info("orphan_documents_cleaned", count=count)
    return count


def _fix_duplicate_entities() -> int:
    """Merge duplicate person entities (same canonical_name, case-insensitive)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Find duplicates
            cur.execute("""
                SELECT LOWER(canonical_name), array_agg(id ORDER BY id) as ids
                FROM entities
                WHERE entity_type = 'person' AND canonical_name IS NOT NULL
                GROUP BY LOWER(canonical_name)
                HAVING COUNT(*) > 1
            """)
            duplicates = cur.fetchall()

            merged = 0
            for canonical_lower, ids in duplicates:
                keep_id = ids[0]  # keep the oldest
                remove_ids = ids[1:]

                for remove_id in remove_ids:
                    # Move chunk_entities
                    cur.execute("""
                        UPDATE chunk_entities SET entity_id = %s
                        WHERE entity_id = %s
                        AND NOT EXISTS (
                            SELECT 1 FROM chunk_entities
                            WHERE entity_id = %s AND chunk_id = chunk_entities.chunk_id
                        )
                    """, (keep_id, remove_id, keep_id))

                    # Move event_entities
                    cur.execute("""
                        UPDATE event_entities SET entity_id = %s
                        WHERE entity_id = %s
                        AND NOT EXISTS (
                            SELECT 1 FROM event_entities
                            WHERE entity_id = %s AND event_id = event_entities.event_id
                        )
                    """, (keep_id, remove_id, keep_id))

                    # Delete orphaned references
                    cur.execute("DELETE FROM chunk_entities WHERE entity_id = %s", (remove_id,))
                    cur.execute("DELETE FROM event_entities WHERE entity_id = %s", (remove_id,))

                    # Delete duplicate entity
                    cur.execute("DELETE FROM entities WHERE id = %s", (remove_id,))
                    merged += 1

            conn.commit()

    if merged > 0:
        log.info("duplicate_entities_merged", count=merged)
    return merged


# ---------------------------------------------------------------------------
# Check functions (detect issues, don't auto-fix)
# ---------------------------------------------------------------------------

def _check_source_staleness() -> list[dict]:
    """Check each source for staleness."""
    issues = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.source_type,
                       MAX(d.created_at) as last_import,
                       EXTRACT(EPOCH FROM NOW() - MAX(d.created_at)) / 3600 as hours_stale
                FROM sources s
                JOIN documents d ON d.source_id = s.id
                GROUP BY s.source_type
                ORDER BY hours_stale DESC
            """)
            for source_type, last_import, hours_stale in cur.fetchall():
                threshold = SOURCE_STALENESS_HOURS.get(source_type, 24)
                if hours_stale and hours_stale > threshold:
                    issues.append({
                        "type": "stale_source",
                        "source": source_type,
                        "hours_stale": round(float(hours_stale), 1),
                        "threshold_hours": threshold,
                        "last_import": last_import.isoformat() if last_import else None,
                        "severity": "critical" if hours_stale > threshold * 3 else "warning",
                    })
    return issues


def _check_extraction_coverage() -> list[dict]:
    """Check for extraction gaps."""
    issues = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Unchecked chunks (neither events nor checked-no-events)
            cur.execute("""
                SELECT COUNT(*) FROM chunks c
                LEFT JOIN events e ON e.chunk_id = c.id
                LEFT JOIN chunks_event_checked cec ON cec.chunk_id = c.id
                WHERE e.id IS NULL AND cec.chunk_id IS NULL
                AND LENGTH(c.text) >= 50
            """)
            unchecked = cur.fetchall()[0][0]

            if unchecked > 500:
                issues.append({
                    "type": "extraction_backlog",
                    "unchecked_chunks": unchecked,
                    "severity": "critical" if unchecked > 5000 else "warning",
                    "note": "Turbo extraction may need more workers or frequency",
                })
            elif unchecked > 100:
                issues.append({
                    "type": "extraction_backlog",
                    "unchecked_chunks": unchecked,
                    "severity": "info",
                })

            # Entity extraction gaps
            cur.execute("""
                SELECT COUNT(*) FROM chunks c
                LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
                LEFT JOIN chunks_entity_checked cec ON cec.chunk_id = c.id
                WHERE ce.id IS NULL AND cec.chunk_id IS NULL
                AND LENGTH(c.text) >= 50
            """)
            entity_unchecked = cur.fetchall()[0][0]

            if entity_unchecked > 500:
                issues.append({
                    "type": "entity_extraction_backlog",
                    "unchecked_chunks": entity_unchecked,
                    "severity": "warning",
                })

    return issues


def _check_low_confidence() -> dict | None:
    """Check for unusual number of low-confidence events."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FILTER (WHERE confidence < 0.5) as low,
                       COUNT(*) as total
                FROM events
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            low, total = cur.fetchone()

    if total > 0 and low / total > 0.1:
        return {
            "type": "high_low_confidence_rate",
            "low_confidence_events": low,
            "total_recent_events": total,
            "pct": round(low / total * 100, 1),
            "severity": "warning",
        }
    return None


# ---------------------------------------------------------------------------
# Quality stats
# ---------------------------------------------------------------------------

def _get_quality_stats() -> dict:
    """Get current data quality statistics."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            stats = {}

            cur.execute("SELECT COUNT(*) FROM chunks")
            stats["total_chunks"] = cur.fetchall()[0][0]

            cur.execute("SELECT COUNT(*) FROM chunks WHERE timestamp_start IS NULL")
            stats["chunks_no_timestamp"] = cur.fetchall()[0][0]

            cur.execute("SELECT COUNT(*) FROM events")
            stats["total_events"] = cur.fetchall()[0][0]

            cur.execute("SELECT COUNT(*) FROM events WHERE event_time IS NULL")
            stats["events_no_timestamp"] = cur.fetchall()[0][0]

            cur.execute("SELECT COUNT(*) FROM entities")
            stats["total_entities"] = cur.fetchall()[0][0]

            cur.execute("SELECT COUNT(*) FROM documents")
            stats["total_documents"] = cur.fetchall()[0][0]

            cur.execute("""
                SELECT COUNT(*) FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                WHERE c.id IS NULL
            """)
            stats["orphan_documents"] = cur.fetchall()[0][0]

            # Extraction coverage
            cur.execute("""
                SELECT COUNT(*) FROM chunks c
                LEFT JOIN events e ON e.chunk_id = c.id
                LEFT JOIN chunks_event_checked cec ON cec.chunk_id = c.id
                WHERE e.id IS NULL AND cec.chunk_id IS NULL
            """)
            stats["unchecked_event_chunks"] = cur.fetchall()[0][0]

            # Coverage percentage
            if stats["total_chunks"] > 0:
                checked = stats["total_chunks"] - stats["unchecked_event_chunks"]
                stats["extraction_coverage_pct"] = round(checked / stats["total_chunks"] * 100, 1)
            else:
                stats["extraction_coverage_pct"] = 0

            # Timestamp coverage
            if stats["total_events"] > 0:
                with_time = stats["total_events"] - stats["events_no_timestamp"]
                stats["timestamp_coverage_pct"] = round(with_time / stats["total_events"] * 100, 1)
            else:
                stats["timestamp_coverage_pct"] = 0

    return stats


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------

def _send_quality_alert(report: dict):
    """Send WhatsApp alert for critical data quality issues."""
    critical = [i for i in report["issues"] if i.get("severity") == "critical"]
    if not critical:
        return

    try:
        from app.delivery.whatsapp import send_whatsapp_message

        lines = ["Data Quality Alert:"]
        for issue in critical:
            if issue["type"] == "stale_source":
                lines.append(f"- {issue['source']}: {issue['hours_stale']}h stale (threshold: {issue['threshold_hours']}h)")
            elif issue["type"] == "extraction_backlog":
                lines.append(f"- Extraction backlog: {issue['unchecked_chunks']} chunks unchecked")

        fixes = report.get("fixes", {})
        total_fixes = sum(v for v in fixes.values() if isinstance(v, int))
        if total_fixes > 0:
            lines.append(f"\nAuto-fixed: {total_fixes} issues")
            for k, v in fixes.items():
                if v > 0:
                    lines.append(f"  - {k}: {v}")

        stats = report.get("stats", {})
        lines.append(f"\nCoverage: extraction {stats.get('extraction_coverage_pct', '?')}%, timestamps {stats.get('timestamp_coverage_pct', '?')}%")

        send_whatsapp_message("\n".join(lines))
        log.info("quality_alert_sent")
    except Exception as e:
        log.warning("quality_alert_failed", error=str(e))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_calibration()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    if result["issues"]:
        print(f"\n{'='*60}")
        print(f"ISSUES FOUND: {len(result['issues'])}")
        for issue in result["issues"]:
            severity = issue.get("severity", "?").upper()
            print(f"  [{severity}] {issue['type']}: {json.dumps({k:v for k,v in issue.items() if k not in ('type','severity')}, ensure_ascii=False)}")

    fixes = result.get("fixes", {})
    total_fixes = sum(v for v in fixes.values() if isinstance(v, int))
    if total_fixes > 0:
        print(f"\nAUTO-FIXED: {total_fixes}")
        for k, v in fixes.items():
            if v > 0:
                print(f"  - {k}: {v}")
