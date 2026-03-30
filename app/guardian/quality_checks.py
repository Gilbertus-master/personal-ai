"""
Data Quality Checks — volume anomaly, duplicate detection, consistency, freshness.

Runs daily at 05:00 UTC (before morning brief).
Computes quality score (0-100) and saves to ingestion_health.
"""

from __future__ import annotations

import os
import statistics
from datetime import datetime, timezone

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger("quality_checks")

# ---------------------------------------------------------------------------
# Qdrant client (lazy, only used for embedding orphan check)
# ---------------------------------------------------------------------------
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "gilbertus_chunks")

ALLOWED_EVENT_TYPES = {
    "conflict", "support", "decision", "meeting", "trade",
    "health", "family", "milestone", "deadline", "commitment",
    "escalation", "blocker", "task_assignment", "approval", "rejection",
}

SLA_HOURS: dict[str, float] = {
    "email": 2.0,
    "email_attachment": 4.0,
    "teams": 2.0,
    "calendar": 4.0,
    "whatsapp_live": 4.0,
    "audio_transcript": 8.0,
    "document": 24.0,
    "whatsapp": 24.0,
    "spreadsheet": 168.0,
}


# ===================================================================
# 1. Volume anomaly detection
# ===================================================================

def check_volume(conn) -> list[dict]:
    """Compare today's doc count vs 7-day average per source."""
    issues: list[dict] = []
    with conn.cursor() as cur:
        cur.execute("""
            WITH daily AS (
                SELECT s.source_type,
                       d.created_at::date AS day,
                       COUNT(*) AS cnt
                FROM documents d
                JOIN sources s ON s.id = d.source_id
                WHERE d.created_at >= NOW() - INTERVAL '8 days'
                GROUP BY s.source_type, d.created_at::date
            ),
            avg7 AS (
                SELECT source_type,
                       AVG(cnt) AS avg_cnt
                FROM daily
                WHERE day < CURRENT_DATE
                GROUP BY source_type
            ),
            today AS (
                SELECT source_type, cnt
                FROM daily
                WHERE day = CURRENT_DATE
            )
            SELECT a.source_type,
                   COALESCE(t.cnt, 0) AS today_cnt,
                   ROUND(a.avg_cnt::numeric, 1) AS avg_7d
            FROM avg7 a
            LEFT JOIN today t USING (source_type)
        """)
        for row in cur.fetchall():
            src, today_cnt, avg_7d = row
            avg_f = float(avg_7d)
            if avg_f == 0:
                continue

            ratio = today_cnt / avg_f
            if today_cnt == 0:
                issues.append({
                    "check": "volume_drop",
                    "source": src,
                    "severity": "critical",
                    "detail": f"0 docs today, 7d avg={avg_7d}",
                })
                log.error("volume_zero", source=src, avg_7d=avg_7d)
            elif ratio < 0.3:
                issues.append({
                    "check": "volume_drop",
                    "source": src,
                    "severity": "warning",
                    "detail": f"{today_cnt} docs today ({ratio:.0%} of avg {avg_7d})",
                })
                log.warning("volume_drop", source=src, today=today_cnt, avg=avg_7d)
            elif ratio > 3.0:
                issues.append({
                    "check": "volume_spike",
                    "source": src,
                    "severity": "warning",
                    "detail": f"{today_cnt} docs today ({ratio:.0%} of avg {avg_7d})",
                })
                log.warning("volume_spike", source=src, today=today_cnt, avg=avg_7d)

    return issues


def check_duplicate_paths(conn) -> list[dict]:
    """Detect duplicate raw_path in documents."""
    issues: list[dict] = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT raw_path, COUNT(*) AS dupes
            FROM documents
            GROUP BY raw_path
            HAVING COUNT(*) > 1
            ORDER BY dupes DESC
            LIMIT 50
        """)
        dupes = cur.fetchall()
        if dupes:
            total = sum(r[1] for r in dupes)
            issues.append({
                "check": "duplicate_paths",
                "severity": "warning",
                "detail": f"{len(dupes)} paths with {total} total duplicates",
            })
            for path, cnt in dupes[:5]:
                log.warning("duplicate_raw_path", path=path, count=cnt)
    return issues


def check_chunk_size_anomaly(conn) -> list[dict]:
    """Detect chunk size anomalies per source (< 50 chars, > 5000 chars, CV > 2 (stdev > 2×mean))."""
    issues: list[dict] = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.source_type,
                   LENGTH(c.text) AS len
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            JOIN sources s ON s.id = d.source_id
            WHERE c.text IS NOT NULL
              AND d.created_at >= NOW() - INTERVAL '7 days'
        """)
        rows = cur.fetchall()

    # Group by source
    by_source: dict[str, list[int]] = {}
    for src, length in rows:
        by_source.setdefault(src, []).append(length)

    for src, lengths in by_source.items():
        tiny = sum(1 for ln in lengths if ln < 50)
        huge = sum(1 for ln in lengths if ln > 5000)

        if tiny > 0:
            issues.append({
                "check": "chunk_too_small",
                "source": src,
                "severity": "warning",
                "detail": f"{tiny} chunks < 50 chars (parser problem?)",
            })
            log.warning("chunk_too_small", source=src, count=tiny)

        if huge > 0:
            issues.append({
                "check": "chunk_too_large",
                "source": src,
                "severity": "warning",
                "detail": f"{huge} chunks > 5000 chars (chunking problem?)",
            })
            log.warning("chunk_too_large", source=src, count=huge)

        if len(lengths) >= 10:
            mean = statistics.mean(lengths)
            stdev = statistics.stdev(lengths)
            if stdev > 0 and stdev > 2 * mean:
                issues.append({
                    "check": "chunk_size_high_variance",
                    "source": src,
                    "severity": "warning",
                    "detail": f"σ={stdev:.0f} > 2×mean={mean:.0f}",
                })
                log.warning("chunk_size_high_variance", source=src, mean=mean, stdev=stdev)

    return issues


# ===================================================================
# 2. Duplicate detection + auto-dedup
# ===================================================================

def check_and_dedup_duplicates(conn) -> list[dict]:
    """Detect and auto-remove exact duplicate chunks (same document + same text)."""
    issues: list[dict] = []
    with conn.cursor() as cur:
        # Find duplicate chunks
        cur.execute("""
            SELECT document_id, text, COUNT(*) AS cnt,
                   ARRAY_AGG(id ORDER BY id DESC) AS ids
            FROM chunks
            GROUP BY document_id, text
            HAVING COUNT(*) > 1
            LIMIT 500
        """)
        dupes = cur.fetchall()

        if not dupes:
            return issues

        total_dupes = sum(r[2] - 1 for r in dupes)
        issues.append({
            "check": "duplicate_chunks",
            "severity": "warning",
            "detail": f"{len(dupes)} groups, {total_dupes} duplicates to remove",
        })

        # Auto-dedup: keep the latest (first in DESC array), delete rest
        ids_to_delete: list[int] = []
        for _doc_id, _text, _cnt, ids in dupes:
            # ids[0] is the latest (highest id) — keep it
            ids_to_delete.extend(ids[1:])

        if ids_to_delete:
            # Delete dependent rows first (chunk_entities, then chunks)
            cur.execute(
                "DELETE FROM chunk_entities WHERE chunk_id = ANY(%s)",
                (ids_to_delete,),
            )
            ce_deleted = cur.rowcount

            cur.execute(
                "DELETE FROM events WHERE chunk_id = ANY(%s)",
                (ids_to_delete,),
            )
            ev_deleted = cur.rowcount

            cur.execute(
                "DELETE FROM chunks WHERE id = ANY(%s)",
                (ids_to_delete,),
            )
            ch_deleted = cur.rowcount
            conn.commit()

            # Remove orphaned Qdrant vectors for deleted chunk IDs
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.models import FieldCondition, Filter, MatchAny

                _qdrant = QdrantClient(
                    url=QDRANT_URL,
                    api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
                    timeout=60,
                )
                _qdrant.delete(
                    collection_name=QDRANT_COLLECTION,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="chunk_id",
                                match=MatchAny(any=ids_to_delete),
                            )
                        ]
                    ),
                )
                log.info("auto_dedup_qdrant_cleanup", chunk_ids_removed=len(ids_to_delete))
            except Exception as _qdrant_err:
                log.warning("auto_dedup_qdrant_cleanup_failed", error=str(_qdrant_err))

            log.info(
                "auto_dedup_chunks",
                chunks_deleted=ch_deleted,
                chunk_entities_deleted=ce_deleted,
                events_deleted=ev_deleted,
            )
            issues.append({
                "check": "auto_dedup",
                "severity": "info",
                "detail": f"Removed {ch_deleted} duplicate chunks, {ce_deleted} chunk_entities, {ev_deleted} events",
            })

    return issues


# ===================================================================
# 3. Consistency checks
# ===================================================================

def check_orphan_chunks(conn) -> list[dict]:
    """Chunks without a parent document."""
    issues: list[dict] = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM chunks c
            LEFT JOIN documents d ON d.id = c.document_id
            WHERE d.id IS NULL
        """)
        cnt = cur.fetchall()[0][0]
        if cnt > 0:
            issues.append({
                "check": "orphan_chunks",
                "severity": "warning",
                "detail": f"{cnt} chunks without parent document",
            })
            log.warning("orphan_chunks", count=cnt)
    return issues


def check_orphan_entities(conn) -> list[dict]:
    """Entities not referenced by any chunk_entity."""
    issues: list[dict] = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM entities e
            LEFT JOIN chunk_entities ce ON ce.entity_id = e.id
            WHERE ce.id IS NULL
        """)
        cnt = cur.fetchall()[0][0]
        if cnt > 0:
            issues.append({
                "check": "orphan_entities",
                "severity": "info",
                "detail": f"{cnt} entities with no chunk references",
            })
            log.info("orphan_entities", count=cnt)
    return issues


def check_invalid_event_types(conn) -> list[dict]:
    """Events with event_type not in the allowed taxonomy."""
    issues: list[dict] = []
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT event_type FROM events")
        all_types = {r[0] for r in cur.fetchall()}
        invalid = all_types - ALLOWED_EVENT_TYPES
        if invalid:
            cur.execute(
                "SELECT event_type, COUNT(*) FROM events WHERE event_type = ANY(%s) GROUP BY event_type",
                (list(invalid),),
            )
            rows = cur.fetchall()
            total = sum(r[1] for r in rows)
            issues.append({
                "check": "invalid_event_types",
                "severity": "warning",
                "detail": f"{total} events with invalid types: {', '.join(sorted(invalid))}",
            })
            log.warning("invalid_event_types", types=sorted(invalid), count=total)
    return issues


def check_embedding_orphans(conn) -> list[dict]:
    """Chunks with embedding_id that have no vector in Qdrant."""
    issues: list[dict] = []
    try:
        from qdrant_client import QdrantClient

        qdrant = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
            timeout=30,
        )
    except Exception as e:
        log.warning("qdrant_unavailable", error=str(e))
        return issues

    with conn.cursor() as cur:
        # Sample up to 500 chunks with embedding_id
        cur.execute("""
            SELECT id, embedding_id FROM chunks
            WHERE embedding_id IS NOT NULL
            ORDER BY id DESC
            LIMIT 500
        """)
        rows = cur.fetchall()

    if not rows:
        return issues

    # Check in batches
    missing = 0
    batch_size = 100
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        point_ids = [r[1] for r in batch]
        try:
            results = qdrant.retrieve(
                collection_name=QDRANT_COLLECTION,
                ids=point_ids,
                with_payload=False,
                with_vectors=False,
            )
            found_ids = {str(p.id) for p in results}
            missing += sum(1 for pid in point_ids if str(pid) not in found_ids)
        except Exception as e:
            log.warning("qdrant_check_failed", error=str(e))
            break

    if missing > 0:
        issues.append({
            "check": "embedding_orphans",
            "severity": "warning",
            "detail": f"{missing}/{len(rows)} sampled chunks have embedding_id but no Qdrant vector",
        })
        log.warning("embedding_orphans", missing=missing, sampled=len(rows))

    return issues


# ===================================================================
# 4. Freshness consistency
# ===================================================================

def check_freshness(conn) -> list[dict]:
    """Check if sources claim fresh but documents are stale."""
    issues: list[dict] = []
    now = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.source_type,
                   MAX(s.imported_at) AS last_import,
                   MAX(d.created_at) AS last_doc
            FROM sources s
            LEFT JOIN documents d ON d.source_id = s.id
            GROUP BY s.source_type
        """)
        for src, last_import, last_doc in cur.fetchall():
            if last_import is None or last_doc is None:
                continue

            sla = SLA_HOURS.get(src, 24.0)
            import_age_h = (now - last_import).total_seconds() / 3600
            doc_age_h = (now - last_doc).total_seconds() / 3600

            # Source says "fresh" (import recent) but docs are old
            if import_age_h < sla and doc_age_h > sla * 3:
                issues.append({
                    "check": "freshness_mismatch",
                    "source": src,
                    "severity": "warning",
                    "detail": f"Source imported {import_age_h:.1f}h ago but latest doc is {doc_age_h:.1f}h old",
                })
                log.warning(
                    "freshness_mismatch",
                    source=src,
                    import_age_h=round(import_age_h, 1),
                    doc_age_h=round(doc_age_h, 1),
                )

    return issues


# ===================================================================
# 5. Quality score (0-100)
# ===================================================================

def compute_quality_score(conn, issues: list[dict]) -> dict:
    """
    Quality score breakdown:
      Freshness   30% — all sources within SLA
      Completeness 25% — extraction + embedding coverage
      Consistency  20% — no orphans, no duplicates
      Volume       15% — within normal range
      Error rate   10% — DLQ size, failed imports
    """
    scores: dict[str, float] = {}
    now = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        # --- Freshness (30%) ---
        cur.execute("""
            SELECT source_type, MAX(imported_at) AS last
            FROM sources
            GROUP BY source_type
        """)
        rows = cur.fetchall()
        if rows:
            within_sla = 0
            total = 0
            for src, last in rows:
                sla = SLA_HOURS.get(src)
                if sla is None:
                    continue
                total += 1
                age_h = (now - last).total_seconds() / 3600
                if age_h <= sla:
                    within_sla += 1
                elif age_h <= sla * 2:
                    within_sla += 0.5
            scores["freshness"] = (within_sla / total * 100) if total > 0 else 100
        else:
            scores["freshness"] = 0

        # --- Completeness (25%) ---
        # Extraction coverage
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM chunks) AS total_chunks,
                (SELECT COUNT(DISTINCT c.id) FROM chunks c
                 LEFT JOIN events e ON e.chunk_id = c.id
                 LEFT JOIN chunks_event_checked cec ON cec.chunk_id = c.id
                 WHERE e.id IS NOT NULL OR cec.chunk_id IS NOT NULL) AS events_processed,
                (SELECT COUNT(*) FROM chunks WHERE embedding_id IS NOT NULL) AS embedded
        """)
        total_chunks, events_processed, embedded = cur.fetchone()
        if total_chunks > 0:
            extraction_pct = events_processed / total_chunks * 100
            embedding_pct = embedded / total_chunks * 100
            scores["completeness"] = (extraction_pct + embedding_pct) / 2
        else:
            scores["completeness"] = 100

        # --- Consistency (20%) ---
        issue_types = {i["check"] for i in issues}
        consistency = 100.0
        if "orphan_chunks" in issue_types:
            consistency -= 30
        if "orphan_entities" in issue_types:
            consistency -= 10
        if "duplicate_chunks" in issue_types:
            consistency -= 20
        if "duplicate_paths" in issue_types:
            consistency -= 15
        if "invalid_event_types" in issue_types:
            consistency -= 15
        if "embedding_orphans" in issue_types:
            consistency -= 10
        scores["consistency"] = max(0, consistency)

        # --- Volume (15%) ---
        volume_issues = [i for i in issues if i["check"].startswith("volume_")]
        if not volume_issues:
            scores["volume"] = 100
        else:
            critical_count = sum(1 for i in volume_issues if i.get("severity") == "critical")
            warning_count = sum(1 for i in volume_issues if i.get("severity") == "warning")
            scores["volume"] = max(0, 100 - critical_count * 30 - warning_count * 15)

        # --- Error rate (10%) ---
        try:
            cur.execute("""
                SELECT COUNT(*) FROM ingestion_dlq
                WHERE status IN ('pending', 'retrying')
            """)
            dlq_count = cur.fetchall()[0][0]
        except Exception:
            conn.rollback()
            dlq_count = 0

        if dlq_count == 0:
            scores["error_rate"] = 100
        elif dlq_count < 5:
            scores["error_rate"] = 80
        elif dlq_count < 20:
            scores["error_rate"] = 50
        else:
            scores["error_rate"] = max(0, 100 - dlq_count * 2)

    # Weighted total
    weights = {
        "freshness": 0.30,
        "completeness": 0.25,
        "consistency": 0.20,
        "volume": 0.15,
        "error_rate": 0.10,
    }
    total_score = sum(scores[k] * weights[k] for k in weights)
    scores["total"] = round(total_score, 1)

    return scores


# ===================================================================
# 6. Save results to ingestion_health
# ===================================================================

def save_quality_report(conn, scores: dict, issues: list[dict]) -> None:
    """Upsert a quality_check row into ingestion_health."""
    today = datetime.now(timezone.utc).date()
    note_lines = []
    for issue in issues[:20]:
        src = issue.get("source", "global")
        note_lines.append(f"[{issue['severity'].upper()}] {issue['check']}/{src}: {issue['detail']}")

    note = "\n".join(note_lines) if note_lines else "All checks passed"
    score_summary = ", ".join(f"{k}={v:.0f}" for k, v in scores.items())
    full_note = f"QualityScore: {score_summary}\n{note}"

    status = "ok"
    if scores["total"] < 50:
        status = "critical"
    elif scores["total"] < 75:
        status = "warning"

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO ingestion_health (check_date, source_type, docs_24h, docs_7d_avg, status, trend, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (check_date, source_type)
            DO UPDATE SET docs_24h = EXCLUDED.docs_24h,
                          status = EXCLUDED.status,
                          note = EXCLUDED.note,
                          created_at = NOW()
        """, (
            today,
            "_quality_check",
            int(scores["total"]),  # abuse docs_24h for score
            0,
            status,
            "stable",
            full_note[:2000],
        ))
    conn.commit()
    log.info("quality_report_saved", score=scores["total"], status=status, issues=len(issues))


# ===================================================================
# Main
# ===================================================================

def run_quality_checks() -> dict:
    """Run all quality checks and return results."""
    log.info("quality_checks_start")
    all_issues: list[dict] = []

    with get_pg_connection() as conn:
        # Volume checks
        all_issues.extend(check_volume(conn))
        all_issues.extend(check_duplicate_paths(conn))
        all_issues.extend(check_chunk_size_anomaly(conn))

        # Duplicate detection + auto-dedup
        all_issues.extend(check_and_dedup_duplicates(conn))

        # Consistency
        all_issues.extend(check_orphan_chunks(conn))
        all_issues.extend(check_orphan_entities(conn))
        all_issues.extend(check_invalid_event_types(conn))
        all_issues.extend(check_embedding_orphans(conn))

        # Freshness
        all_issues.extend(check_freshness(conn))

        # Quality score
        scores = compute_quality_score(conn, all_issues)

        # Save
        save_quality_report(conn, scores, all_issues)

    critical = [i for i in all_issues if i.get("severity") == "critical"]
    warnings = [i for i in all_issues if i.get("severity") == "warning"]

    log.info(
        "quality_checks_done",
        score=scores["total"],
        critical=len(critical),
        warnings=len(warnings),
        total_issues=len(all_issues),
    )

    return {
        "score": scores,
        "issues": all_issues,
        "critical": len(critical),
        "warnings": len(warnings),
    }


if __name__ == "__main__":
    from app.log_config import setup_logging
    setup_logging()

    result = run_quality_checks()
    print(f"\n{'='*60}")
    print(f"Quality Score: {result['score']['total']}/100")
    print(f"  Freshness:    {result['score']['freshness']:.0f}")
    print(f"  Completeness: {result['score']['completeness']:.0f}")
    print(f"  Consistency:  {result['score']['consistency']:.0f}")
    print(f"  Volume:       {result['score']['volume']:.0f}")
    print(f"  Error rate:   {result['score']['error_rate']:.0f}")
    print(f"Critical: {result['critical']}, Warnings: {result['warnings']}")
    if result["issues"]:
        print("\nIssues:")
        for issue in result["issues"]:
            src = issue.get("source", "global")
            print(f"  [{issue['severity'].upper()}] {issue['check']}/{src}: {issue['detail']}")
    print(f"{'='*60}")
