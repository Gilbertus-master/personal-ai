"""CRUD operations for the process candidate review queue."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import psycopg
import psycopg.rows
import structlog

log = structlog.get_logger(__name__)


def list_pending(
    conn: psycopg.Connection, limit: int = 50
) -> list[dict]:
    """List pending process candidates ordered by frequency."""
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """SELECT
                   candidate_id, pattern_hash, sequence, source, entity_type,
                   project_keys, occurrences_count, occurrences_per_week,
                   avg_duration_h, p90_duration_h, unique_actors_count,
                   suggested_name, suggested_description, suggested_type,
                   suggested_metrics, llm_confidence, created_at
               FROM process_candidates
               WHERE status = 'pending'
               ORDER BY occurrences_per_week DESC
               LIMIT %s""",
            (limit,),
        )
        return cur.fetchall()


def approve_candidate(
    conn: psycopg.Connection,
    candidate_id: UUID,
    name_override: Optional[str] = None,
    reviewed_by: Optional[UUID] = None,
) -> UUID:
    """
    Approve a candidate: create a process in the processes table,
    update the candidate status.
    Returns the new process_id.
    """
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        # Fetch the candidate
        cur.execute(
            """SELECT * FROM process_candidates
               WHERE candidate_id = %s AND status = 'pending'""",
            (candidate_id,),
        )
        candidate = cur.fetchone()
        if not candidate:
            raise ValueError(
                f"Candidate {candidate_id} not found or not pending"
            )

        process_name = name_override or candidate["suggested_name"] or "Unnamed Process"
        process_type = candidate.get("suggested_type") or "operations"

        # Validate process_type against processes table constraint
        valid_types = {"engineering", "sales", "customer_service", "finance", "operations"}
        if process_type not in valid_types:
            process_type = "operations"

        # Create the process
        cur.execute(
            """INSERT INTO processes (process_name, process_type, process_category)
               VALUES (%s, %s, %s)
               RETURNING process_id""",
            (process_name, process_type, candidate["source"]),
        )
        row = cur.fetchone()
        process_id = row["process_id"]

        # Update candidate
        cur.execute(
            """UPDATE process_candidates
               SET status = 'approved',
                   merged_into_process_id = %s,
                   reviewed_by = %s,
                   reviewed_at = %s
               WHERE candidate_id = %s""",
            (
                process_id,
                reviewed_by,
                datetime.now(timezone.utc),
                candidate_id,
            ),
        )

    conn.commit()
    log.info(
        "candidate_approved",
        candidate_id=str(candidate_id),
        process_id=str(process_id),
        name=process_name,
    )
    return process_id


def reject_candidate(
    conn: psycopg.Connection,
    candidate_id: UUID,
    reason: str,
    reviewed_by: Optional[UUID] = None,
) -> None:
    """Reject a candidate with a reason."""
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE process_candidates
               SET status = 'rejected',
                   rejection_reason = %s,
                   reviewed_by = %s,
                   reviewed_at = %s
               WHERE candidate_id = %s AND status = 'pending'""",
            (
                reason,
                reviewed_by,
                datetime.now(timezone.utc),
                candidate_id,
            ),
        )
        if cur.rowcount == 0:
            raise ValueError(
                f"Candidate {candidate_id} not found or not pending"
            )
    conn.commit()
    log.info(
        "candidate_rejected",
        candidate_id=str(candidate_id),
        reason=reason,
    )


def merge_candidates(
    conn: psycopg.Connection,
    candidate_ids: list[UUID],
    merged_name: str,
    reviewed_by: Optional[UUID] = None,
) -> UUID:
    """
    Merge multiple candidates into a single process.
    Creates one process, marks all candidates as 'merged'.
    Returns the new process_id.
    """
    if len(candidate_ids) < 2:
        raise ValueError("Need at least 2 candidates to merge")

    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        # Fetch all candidates
        cur.execute(
            """SELECT * FROM process_candidates
               WHERE candidate_id = ANY(%s) AND status = 'pending'""",
            (candidate_ids,),
        )
        candidates = cur.fetchall()

        if len(candidates) != len(candidate_ids):
            found = {str(c["candidate_id"]) for c in candidates}
            missing = [
                str(cid)
                for cid in candidate_ids
                if str(cid) not in found
            ]
            raise ValueError(
                f"Some candidates not found or not pending: {missing}"
            )

        # Determine best type from candidates
        type_counts: dict[str, int] = {}
        for c in candidates:
            t = c.get("suggested_type") or "operations"
            type_counts[t] = type_counts.get(t, 0) + c["occurrences_count"]
        best_type = max(type_counts, key=type_counts.get)  # type: ignore[arg-type]

        valid_types = {"engineering", "sales", "customer_service", "finance", "operations"}
        if best_type not in valid_types:
            best_type = "operations"

        # Aggregate source from the most frequent candidate
        best_source = max(candidates, key=lambda c: c["occurrences_count"])["source"]

        # Create merged process
        cur.execute(
            """INSERT INTO processes (process_name, process_type, process_category)
               VALUES (%s, %s, %s)
               RETURNING process_id""",
            (merged_name, best_type, best_source),
        )
        row = cur.fetchone()
        process_id = row["process_id"]

        # Mark all as merged
        now = datetime.now(timezone.utc)
        cur.execute(
            """UPDATE process_candidates
               SET status = 'merged',
                   merged_into_process_id = %s,
                   reviewed_by = %s,
                   reviewed_at = %s
               WHERE candidate_id = ANY(%s)""",
            (process_id, reviewed_by, now, candidate_ids),
        )

    conn.commit()
    log.info(
        "candidates_merged",
        candidate_ids=[str(c) for c in candidate_ids],
        process_id=str(process_id),
        name=merged_name,
    )
    return process_id


def auto_approve(
    conn: psycopg.Connection,
    min_confidence: float = 0.9,
) -> int:
    """Auto-approve all pending candidates with llm_confidence >= threshold."""
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """SELECT candidate_id, suggested_name, suggested_type
               FROM process_candidates
               WHERE status = 'pending'
                 AND llm_confidence >= %s""",
            (min_confidence,),
        )
        rows = cur.fetchall()

    approved = 0
    for row in rows:
        try:
            approve_candidate(
                conn,
                row["candidate_id"],
                name_override=row.get("suggested_name"),
            )
            approved += 1
        except Exception as exc:
            log.error(
                "auto_approve_failed",
                candidate_id=str(row["candidate_id"]),
                error=str(exc),
            )

    log.info(
        "auto_approve_done",
        threshold=min_confidence,
        approved=approved,
        eligible=len(rows),
    )
    return approved
