"""Sequence mining — discover recurring state-transition patterns from process_events."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

import psycopg
import psycopg.rows
import structlog

from process_discovery.models import ProcessCandidate

log = structlog.get_logger(__name__)


def _pattern_hash(source: str, entity_type: str, sequence: list[str]) -> str:
    """Deterministic hash for a (source, entity_type, sequence) tuple."""
    payload = f"{source}|{entity_type}|{'->'.join(sorted(sequence))}"
    return hashlib.md5(payload.encode()).hexdigest()


def _remove_consecutive_dupes(seq: list[str]) -> list[str]:
    """Remove consecutive duplicate states: [a,a,b,b,c] -> [a,b,c]."""
    if not seq:
        return seq
    result = [seq[0]]
    for s in seq[1:]:
        if s != result[-1]:
            result.append(s)
    return result


def _canonicalize(seq: list[str]) -> list[str]:
    """Truncate at first terminal state (done/cancelled)."""
    terminals = {"done", "cancelled"}
    result: list[str] = []
    for s in seq:
        result.append(s)
        if s in terminals:
            break
    return result


def mine_sequences(
    conn: psycopg.Connection,
    source: Optional[str] = None,
    since: Optional[datetime] = None,
    min_occurrences: int = 10,
    min_per_week: float = 2.0,
) -> list[ProcessCandidate]:
    """
    Mine recurring state-transition sequences from process_events.

    Algorithm:
    1. Group events by entity_id -> ordered state_group sequences
    2. Normalize: remove consecutive duplicates, truncate at terminal states
    3. Filter: length 2-8, not trivial
    4. Count occurrences, compute stats
    5. Return ProcessCandidate objects for frequent patterns
    """
    log.info(
        "mine_sequences_start",
        source=source,
        since=since.isoformat() if since else None,
        min_occurrences=min_occurrences,
        min_per_week=min_per_week,
    )

    # Step 1: Get entity sequences in batches
    where_clauses = ["state_group IS NOT NULL"]
    params: list = []

    if source:
        where_clauses.append("source = %s")
        params.append(source)
    if since:
        where_clauses.append("occurred_at >= %s")
        params.append(since)

    where_sql = " AND ".join(where_clauses)

    # Get total entity count for batching
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT COUNT(DISTINCT entity_id)
                FROM process_events
                WHERE {where_sql}""",
            params,
        )
        row = cur.fetchone()
        total_entities = row[0] if row else 0

    if total_entities == 0:
        log.info("mine_sequences_no_entities")
        return []

    # Get date range for per-week calculation
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT MIN(occurred_at), MAX(occurred_at)
                FROM process_events
                WHERE {where_sql}""",
            params,
        )
        row = cur.fetchone()
        if not row or not row[0] or not row[1]:
            return []
        min_date, max_date = row[0], row[1]

    span_weeks = max(
        1.0, (max_date - min_date).total_seconds() / (7 * 24 * 3600)
    )

    # Step 2-3: Extract and normalize sequences in batches
    # pattern_key -> { occurrences: [entity_ids], durations: [...], actors: set }
    pattern_stats: dict[str, dict] = {}

    batch_size = 10_000
    offset = 0

    while offset < total_entities:
        entity_batch_query = f"""
            WITH entity_batch AS (
                SELECT DISTINCT entity_id
                FROM process_events
                WHERE {where_sql}
                ORDER BY entity_id
                LIMIT %s OFFSET %s
            )
            SELECT
                pe.source,
                pe.entity_type,
                pe.entity_id,
                array_agg(pe.state_group ORDER BY pe.occurred_at) AS seq,
                array_agg(DISTINCT pe.project_key)
                    FILTER (WHERE pe.project_key IS NOT NULL) AS project_keys,
                EXTRACT(EPOCH FROM (MAX(pe.occurred_at) - MIN(pe.occurred_at))) / 3600.0
                    AS total_duration_h,
                array_agg(DISTINCT pe.actor_person_id::text)
                    FILTER (WHERE pe.actor_person_id IS NOT NULL) AS actor_ids
            FROM process_events pe
            JOIN entity_batch eb ON eb.entity_id = pe.entity_id
            WHERE {where_sql}
            GROUP BY pe.source, pe.entity_type, pe.entity_id
        """
        batch_params = params + [batch_size, offset] + params

        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(entity_batch_query, batch_params)
            rows = cur.fetchall()

        for row in rows:
            raw_seq = row["seq"]
            if not raw_seq:
                continue

            # Normalize
            seq = _remove_consecutive_dupes(raw_seq)
            seq = _canonicalize(seq)

            # Filter: length 2-8, not trivial
            if len(seq) < 2 or len(seq) > 8:
                continue
            if seq == ["todo", "done"]:
                continue

            src = row["source"]
            etype = row["entity_type"]
            phash = _pattern_hash(src, etype, seq)
            key = phash

            if key not in pattern_stats:
                pattern_stats[key] = {
                    "sequence": seq,
                    "source": src,
                    "entity_type": etype,
                    "project_keys": set(),
                    "durations": [],
                    "actors": set(),
                    "count": 0,
                }

            stats = pattern_stats[key]
            stats["count"] += 1
            if row.get("project_keys"):
                stats["project_keys"].update(
                    pk for pk in row["project_keys"] if pk
                )
            if row.get("total_duration_h") is not None:
                stats["durations"].append(row["total_duration_h"])
            if row.get("actor_ids"):
                stats["actors"].update(
                    aid for aid in row["actor_ids"] if aid
                )

        offset += batch_size
        log.debug("mine_sequences_batch", offset=offset, total=total_entities)

    # Step 4-5: Filter by frequency and build candidates
    candidates: list[ProcessCandidate] = []

    for phash, stats in pattern_stats.items():
        count = stats["count"]
        per_week = count / span_weeks

        if count < min_occurrences or per_week < min_per_week:
            continue

        durations = sorted(stats["durations"]) if stats["durations"] else []
        avg_dur = sum(durations) / len(durations) if durations else None
        p90_dur = (
            durations[int(len(durations) * 0.9)] if durations else None
        )

        candidate = ProcessCandidate(
            pattern_hash=phash,
            sequence=stats["sequence"],
            source=stats["source"],
            entity_type=stats["entity_type"],
            project_keys=sorted(stats["project_keys"]),
            occurrences_count=count,
            occurrences_per_week=round(per_week, 2),
            avg_duration_h=round(avg_dur, 2) if avg_dur is not None else None,
            p90_duration_h=round(p90_dur, 2) if p90_dur is not None else None,
            unique_actors_count=len(stats["actors"]),
        )
        candidates.append(candidate)

    # Sort by frequency descending
    candidates.sort(key=lambda c: c.occurrences_per_week, reverse=True)

    log.info(
        "mine_sequences_done",
        total_patterns=len(pattern_stats),
        candidates_passing_filter=len(candidates),
        span_weeks=round(span_weeks, 1),
    )
    return candidates


def save_candidates(
    conn: psycopg.Connection, candidates: list[ProcessCandidate]
) -> int:
    """Insert or update candidates in process_candidates. Returns count of new rows."""
    if not candidates:
        return 0

    inserted = 0
    with conn.cursor() as cur:
        for c in candidates:
            cur.execute(
                """INSERT INTO process_candidates
                   (pattern_hash, sequence, source, entity_type, project_keys,
                    occurrences_count, occurrences_per_week, avg_duration_h,
                    p90_duration_h, unique_actors_count,
                    suggested_name, suggested_description, suggested_type,
                    suggested_metrics, llm_confidence)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           %s, %s, %s, %s, %s)
                   ON CONFLICT (pattern_hash) DO UPDATE SET
                       occurrences_count = EXCLUDED.occurrences_count,
                       occurrences_per_week = EXCLUDED.occurrences_per_week,
                       avg_duration_h = EXCLUDED.avg_duration_h,
                       p90_duration_h = EXCLUDED.p90_duration_h,
                       unique_actors_count = EXCLUDED.unique_actors_count,
                       suggested_name = COALESCE(
                           EXCLUDED.suggested_name,
                           process_candidates.suggested_name
                       ),
                       suggested_description = COALESCE(
                           EXCLUDED.suggested_description,
                           process_candidates.suggested_description
                       ),
                       suggested_type = COALESCE(
                           EXCLUDED.suggested_type,
                           process_candidates.suggested_type
                       ),
                       suggested_metrics = COALESCE(
                           EXCLUDED.suggested_metrics,
                           process_candidates.suggested_metrics
                       ),
                       llm_confidence = COALESCE(
                           EXCLUDED.llm_confidence,
                           process_candidates.llm_confidence
                       )
                   RETURNING (xmax = 0) AS is_insert""",
                (
                    c.pattern_hash,
                    c.sequence,
                    c.source,
                    c.entity_type,
                    c.project_keys,
                    c.occurrences_count,
                    c.occurrences_per_week,
                    c.avg_duration_h,
                    c.p90_duration_h,
                    c.unique_actors_count,
                    c.suggested_name,
                    c.suggested_description,
                    c.suggested_type,
                    c.suggested_metrics,
                    c.llm_confidence,
                ),
            )
            row = cur.fetchone()
            if row and row[0]:
                inserted += 1

    conn.commit()
    log.info("save_candidates_done", inserted=inserted, updated=len(candidates) - inserted)
    return inserted
