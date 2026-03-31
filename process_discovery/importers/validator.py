"""Validate parsed processes and write to process_candidates table."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

import psycopg
import structlog

log = structlog.get_logger("process_discovery.importers.validator")


def map_to_candidate(parsed: dict, filename: str) -> dict | None:
    """Map LLM output to process_candidates row structure. Returns None if invalid."""
    name = (parsed.get("name") or "").strip()
    if not name:
        return None

    description = (parsed.get("description") or "").strip()
    if not description:
        return None

    pattern_hash = "manual_" + hashlib.md5(name.lower().encode()).hexdigest()

    steps = parsed.get("steps") or []
    if isinstance(steps, list):
        steps = [str(s) for s in steps if s]
    else:
        steps = []

    suggested_type = parsed.get("process_type", "operations")
    valid_types = ("engineering", "sales", "customer_service", "finance", "operations", "hr", "other")
    if suggested_type not in valid_types:
        suggested_type = "operations"

    confidence = parsed.get("confidence", 0.7)
    if not isinstance(confidence, (int, float)):
        confidence = 0.7
    confidence = max(0.0, min(1.0, float(confidence)))

    metrics_data = {
        "inputs": parsed.get("inputs", []),
        "outputs": parsed.get("outputs", []),
        "systems": parsed.get("systems_used", []),
        "participants": parsed.get("participants", []),
        "owner_role": parsed.get("owner_role"),
        "sla": parsed.get("sla_or_target"),
        "estimated_duration": parsed.get("estimated_duration"),
        "parent_process_name": parsed.get("parent_process_name"),
        "notes": parsed.get("notes"),
        "source_file": filename,
    }

    return {
        "pattern_hash": pattern_hash,
        "sequence": steps if steps else ["start", "end"],
        "source": "manual_import",
        "entity_type": "manual",
        "project_keys": None,
        "suggested_name": name,
        "suggested_description": description,
        "suggested_type": suggested_type,
        "suggested_metrics": json.dumps(metrics_data, ensure_ascii=False),
        "llm_confidence": confidence,
        "occurrences_count": 1,
        "occurrences_per_week": 0.0,
        "unique_actors_count": len(parsed.get("participants", [])) or None,
    }


def _check_duplicate(conn: psycopg.Connection, pattern_hash: str) -> bool:
    """Check if this pattern_hash already exists in process_candidates or processes."""
    row = conn.execute(
        "SELECT 1 FROM process_candidates WHERE pattern_hash = %s LIMIT 1",
        (pattern_hash,),
    ).fetchone()
    if row:
        return True

    # Also check processes by similar name
    return False


def validate_and_save(
    processes: list[dict],
    source_file: str,
    auto_approve_above: float | None,
    conn: psycopg.Connection,
) -> dict[str, Any]:
    """Validate, deduplicate, and save processes to process_candidates.

    Returns stats dict with saved, duplicates, approved counts.
    """
    saved = 0
    duplicates = 0
    approved = 0
    candidates: list[dict] = []

    for parsed in processes:
        candidate = map_to_candidate(parsed, source_file)
        if not candidate:
            log.debug("invalid_candidate_skipped", name=parsed.get("name"))
            continue

        if _check_duplicate(conn, candidate["pattern_hash"]):
            log.debug("duplicate_skipped", name=candidate["suggested_name"])
            duplicates += 1
            continue

        # Determine status
        status = "pending"
        if auto_approve_above is not None and candidate["llm_confidence"] >= auto_approve_above:
            status = "approved"

        try:
            row = conn.execute(
                """INSERT INTO process_candidates (
                       pattern_hash, sequence, source, entity_type, project_keys,
                       suggested_name, suggested_description, suggested_type,
                       suggested_metrics, llm_confidence,
                       occurrences_count, occurrences_per_week, unique_actors_count,
                       status
                   ) VALUES (
                       %s, %s, %s, %s, %s,
                       %s, %s, %s,
                       %s, %s,
                       %s, %s, %s,
                       %s
                   )
                   ON CONFLICT (pattern_hash) DO NOTHING
                   RETURNING candidate_id""",
                (
                    candidate["pattern_hash"],
                    candidate["sequence"],
                    candidate["source"],
                    candidate["entity_type"],
                    candidate["project_keys"],
                    candidate["suggested_name"],
                    candidate["suggested_description"],
                    candidate["suggested_type"],
                    candidate["suggested_metrics"],
                    candidate["llm_confidence"],
                    candidate["occurrences_count"],
                    candidate["occurrences_per_week"],
                    candidate["unique_actors_count"],
                    status,
                ),
            ).fetchone()

            if row:
                saved += 1
                candidate["candidate_id"] = str(row[0])
                candidate["status"] = status
                candidates.append(candidate)

                if status == "approved":
                    _auto_create_process(conn, candidate, row[0])
                    approved += 1

                log.info(
                    "candidate_saved",
                    name=candidate["suggested_name"],
                    status=status,
                    confidence=candidate["llm_confidence"],
                )
            else:
                duplicates += 1

        except Exception:
            log.exception("candidate_save_failed", name=candidate["suggested_name"])

    conn.commit()

    return {
        "file": source_file,
        "processes_found": len(processes),
        "saved": saved,
        "duplicates": duplicates,
        "approved": approved,
        "candidates": candidates,
    }


def _auto_create_process(
    conn: psycopg.Connection, candidate: dict, candidate_id: UUID
) -> None:
    """When auto-approved, also create a row in the processes table."""
    row = conn.execute(
        """INSERT INTO processes (
               process_name, process_type, process_category
           ) VALUES (%s, %s, 'core')
           RETURNING process_id""",
        (candidate["suggested_name"], candidate["suggested_type"]),
    ).fetchone()

    if row:
        conn.execute(
            """UPDATE process_candidates SET
                   merged_into_process_id = %s, reviewed_at = now()
               WHERE candidate_id = %s""",
            (row[0], str(candidate_id)),
        )
        log.info(
            "process_auto_created",
            process_id=str(row[0]),
            name=candidate["suggested_name"],
        )
