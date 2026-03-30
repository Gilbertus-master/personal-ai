"""
Commitment Extraction — extracts promises, agreements, and task assignments from chunks.

Looks for:
- Explicit promises: "zrobię", "dostarczę", "przygotuję", "wyślę"
- Agreements: "ok, to zrobię do piątku"
- Task assignments: "Roch ma przygotować raport"
- Deadlines: "do końca tygodnia", "do 15 kwietnia"
- Meeting action items

Uses Claude Haiku with tool_use, same pattern as events.py.
"""
import signal
import sys
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv

log = structlog.get_logger("extraction.commitments")

_shutdown_requested = False


def _handle_sigterm(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    log.info("sigterm_received", msg="Graceful shutdown requested — finishing current chunk...")


signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)

from app.extraction.llm_client import LLMExtractionClient  # noqa: E402
from app.db.postgres import get_pg_connection  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

DEFAULT_LIMIT = 50
MIN_TEXT_LENGTH = 50

COMMITMENT_SYSTEM_PROMPT = """
You extract commitments, promises, and task assignments from text chunks.

Rules:
- Return a commitment if someone explicitly promises, agrees, or is assigned to do something.
- Look for:
  - Explicit promises: "zrobię", "dostarczę", "przygotuję", "wyślę", "zajmę się", "dam znać"
  - Agreements: "ok, to zrobię do piątku", "jasne, wyślę jutro"
  - Task assignments: "Roch ma przygotować raport", "Krystian zajmie się tym"
  - Deadlines: "do końca tygodnia", "do 15 kwietnia", "before Friday"
  - Meeting action items: assigned tasks from meeting notes
- Do NOT return commitments for: vague statements ("maybe I'll look into it"), questions, hypotheticals, past completed actions.
- person_name: the person who committed or was assigned the task.
- commitment_text: short, factual description of what was committed.
- deadline: if a deadline is mentioned, format as YYYY-MM-DD. If no deadline, return null.
- confidence: 0.0-1.0, how confident you are this is a real commitment.
- If no commitment found, return commitment = null.
""".strip()

COMMITMENT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "commitment": {
            "anyOf": [
                {
                    "type": "object",
                    "properties": {
                        "person_name": {"type": "string", "description": "Who made the commitment"},
                        "commitment_text": {"type": "string", "description": "What was committed"},
                        "deadline": {"type": "string", "description": "Deadline if mentioned (YYYY-MM-DD or null)", "nullable": True},
                        "confidence": {"type": "number"},
                    },
                    "required": ["person_name", "commitment_text", "confidence"],
                    "additionalProperties": False,
                },
                {"type": "null"},
            ]
        }
    },
    "required": ["commitment"],
    "additionalProperties": False,
}


_tables_ensured = False
def _ensure_tables() -> None:
    """Create commitment-related tables if they don't exist."""
    global _tables_ensured
    if _tables_ensured:
        return
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS commitments (
                    id BIGSERIAL PRIMARY KEY,
                    person_name TEXT NOT NULL,
                    person_id BIGINT,
                    commitment_text TEXT NOT NULL,
                    context TEXT,
                    deadline DATE,
                    source_chunk_id BIGINT,
                    source_event_id BIGINT,
                    status TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'fulfilled', 'broken', 'overdue', 'cancelled')),
                    fulfilled_evidence TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_commitments_status ON commitments(status)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_commitments_person ON commitments(person_name)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_commitments_deadline ON commitments(deadline)
                    WHERE status = 'open'
            """)
            cur.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'commitments'
                          AND column_name = 'deadline'
                          AND data_type = 'timestamp with time zone'
                    ) THEN
                        ALTER TABLE commitments
                            ALTER COLUMN deadline TYPE DATE USING deadline::DATE;
                    END IF;
                END$$
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chunks_commitment_checked (
                    chunk_id BIGINT PRIMARY KEY,
                    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        conn.commit()
    log.info("tables_ensured", tables=["commitments", "chunks_commitment_checked"])
    _tables_ensured = True


def parse_args() -> tuple[int, int, int, str | None]:
    """Parse CLI args: --limit N, --worker N, --total N, --model MODEL."""
    limit = DEFAULT_LIMIT
    worker_id = 0
    worker_total = 1
    model_override = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        elif args[i] == "--worker" and i + 1 < len(args):
            worker_id = int(args[i + 1])
            i += 2
        elif args[i] == "--total" and i + 1 < len(args):
            worker_total = int(args[i + 1])
            i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model_override = args[i + 1]
            i += 2
        else:
            i += 1

    return limit, worker_id, worker_total, model_override


def fetch_candidate_chunks(
    limit: int,
    worker_id: int = 0,
    worker_total: int = 1,
) -> list[dict[str, Any]]:
    """Fetch chunks not yet checked for commitments."""
    partition_clause = ""
    if worker_total > 1:
        partition_clause = f"AND c.id %% {worker_total} = {worker_id}"

    sql = f"""
    SELECT c.id, c.document_id, c.chunk_index, c.timestamp_start, c.text
    FROM chunks c
    LEFT JOIN chunks_commitment_checked ccc ON ccc.chunk_id = c.id
    WHERE ccc.chunk_id IS NULL
      AND length(c.text) >= {MIN_TEXT_LENGTH}
      {partition_clause}
    ORDER BY c.id
    LIMIT %s
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()

    return [
        {
            "chunk_id": row[0],
            "document_id": row[1],
            "chunk_index": row[2],
            "timestamp_start": str(row[3]) if row[3] else "",
            "text": row[4],
        }
        for row in rows
    ]


def detect_commitment_with_llm(llm: LLMExtractionClient, text: str) -> dict[str, Any] | None:
    """Use LLM to detect a commitment in chunk text."""
    payload = f"Chunk text:\n{text[:6000]}"

    parsed = llm.extract_object(
        system_prompt=COMMITMENT_SYSTEM_PROMPT,
        user_payload=payload,
        tool_name="return_commitment",
        tool_description="Return a commitment/promise/task assignment or null",
        input_schema=COMMITMENT_TOOL_SCHEMA,
    )

    raw = parsed.get("commitment")
    if raw is None or not isinstance(raw, dict):
        return None

    person_name = str(raw.get("person_name", "")).strip()
    commitment_text = str(raw.get("commitment_text", "")).strip()

    if not person_name or not commitment_text:
        return None

    try:
        confidence = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))

    if confidence < 0.3:
        return None

    deadline = raw.get("deadline")
    if deadline and not isinstance(deadline, str):
        deadline = None

    return {
        "person_name": person_name,
        "commitment_text": commitment_text[:500],
        "deadline": deadline,
        "confidence": confidence,
    }


def resolve_person_id(person_name: str) -> int | None:
    """Try to resolve person_name to a people.id."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id FROM people p
                JOIN entities e ON e.id = p.entity_id
                WHERE LOWER(e.canonical_name) = LOWER(%s)
                LIMIT 1
                """,
                (person_name,),
            )
            rows = cur.fetchall()
    return rows[0][0] if rows else None


def insert_commitment(
    person_name: str,
    person_id: int | None,
    commitment_text: str,
    context: str | None,
    deadline: str | None,
    source_chunk_id: int,
) -> int:
    """Insert a commitment into the DB."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO commitments
                    (person_name, person_id, commitment_text, context, deadline, source_chunk_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'open')
                RETURNING id
                """,
                (person_name, person_id, commitment_text, context, deadline, source_chunk_id),
            )
            commitment_id = cur.fetchall()[0][0]
        conn.commit()
    return commitment_id


def mark_commitment_checked(chunk_id: int) -> None:
    """Mark a chunk as checked for commitments (negative result)."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chunks_commitment_checked (chunk_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (chunk_id,),
            )
        conn.commit()


def _create_extraction_run(model: str, worker_id: int, worker_total: int, batch_size: int) -> int | None:
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO extraction_runs (module, model, worker_id, worker_total, batch_size)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    ("commitments", model, worker_id, worker_total, batch_size),
                )
                run_id = cur.fetchall()[0][0]
            conn.commit()
        return run_id
    except Exception as e:
        log.warning("extraction_run_create_failed", error=str(e))
        return None


def _finish_extraction_run(run_id: int | None, processed: int, created: int, negative: int) -> None:
    if run_id is None:
        return
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE extraction_runs
                       SET chunks_processed=%s, items_created=%s, items_negative=%s,
                           finished_at=NOW(), status='completed'
                       WHERE id=%s""",
                    (processed, created, negative, run_id),
                )
            conn.commit()
    except Exception as e:
        log.warning("extraction_run_finish_failed", run_id=run_id, error=str(e))


def main() -> None:
    limit, worker_id, worker_total, model_override = parse_args()

    _ensure_tables()

    llm = LLMExtractionClient(model_override=model_override, module="extraction.commitments")

    rows = fetch_candidate_chunks(
        limit=limit,
        worker_id=worker_id,
        worker_total=worker_total,
    )
    log.info("chunks_to_process", count=len(rows), worker=worker_id, total=worker_total)

    run_id = _create_extraction_run(llm.model, worker_id, worker_total, limit)

    processed = 0
    commitments_written = 0

    for row in rows:
        if _shutdown_requested:
            log.info("shutdown_stopping", processed=processed)
            break

        chunk_id = row["chunk_id"]
        text = row["text"] or ""

        try:
            detected = detect_commitment_with_llm(llm, text)
        except Exception as e:
            log.error("llm_call_failed", chunk_id=chunk_id, error=str(e))
            processed += 1
            continue

        log.info(
            "chunk_processed",
            chunk_id=chunk_id,
            commitment_detected=bool(detected),
            person=detected["person_name"] if detected else None,
        )

        if detected:
            person_id = resolve_person_id(detected["person_name"])
            context_snippet = text[:300] if text else None

            insert_commitment(
                person_name=detected["person_name"],
                person_id=person_id,
                commitment_text=detected["commitment_text"],
                context=context_snippet,
                deadline=detected.get("deadline"),
                source_chunk_id=chunk_id,
            )
            commitments_written += 1

        mark_commitment_checked(chunk_id)
        processed += 1

    _finish_extraction_run(run_id, processed, commitments_written, processed - commitments_written)

    log.info(
        "extraction_complete",
        processed_chunks=processed,
        commitments_written=commitments_written,
        extraction_run_id=run_id,
    )


if __name__ == "__main__":
    main()
