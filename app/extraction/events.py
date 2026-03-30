import json
import signal
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_shutdown_requested = False


def _handle_sigterm(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True
    print("[SIGTERM] Graceful shutdown requested — finishing current chunk...")


signal.signal(signal.SIGTERM, _handle_sigterm)
signal.signal(signal.SIGINT, _handle_sigterm)

from app.extraction.llm_client import LLMExtractionClient  # noqa: E402
from app.extraction.taxonomy import EVENT_TYPES  # noqa: E402
from app.db.postgres import get_pg_connection  # noqa: E402


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


DEFAULT_LIMIT = 50


EVENT_SYSTEM_PROMPT = """
You extract one timeline-worthy event from a chunk of text.

Rules:
- Return an event if the chunk describes a concrete occurrence: a decision made, a meeting held, a trade executed, a conflict or disagreement, a supportive action, a health development, or a family-relevant occurrence.
- Also capture: commitments, deadlines, task assignments, status updates about specific projects, negotiations, escalations, approvals, rejections, and any action someone took or agreed to take.
- Do NOT return events for: generic advice with no specific context, abstract educational explanations, dictionary definitions, recipes, or purely hypothetical scenarios.
- Use only these event_type values:
  conflict, support, decision, meeting, trade, health, family, milestone,
  deadline, commitment, escalation, blocker, task_assignment, approval, rejection
- If the chunk is genuinely not event-worthy, return event = null.
- confidence must be between 0 and 1.
- summary must be short, factual, and in the language of the chunk.
- event_date: If the text contains a specific date/time for the event (e.g. "2025-03-15", "w piątek 14:00", "January 2025"), extract it as ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM). If no date is mentioned, return null.
""".strip()


EVENT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "event": {
            "anyOf": [
                {
                    "type": "object",
                    "properties": {
                        "event_type": {
                            "type": "string",
                            "enum": ["conflict", "support", "decision", "meeting", "trade", "health", "family", "milestone", "deadline", "commitment", "escalation", "blocker", "task_assignment", "approval", "rejection"],
                        },
                        "summary": {"type": "string"},
                        "confidence": {"type": "number"},
                        "event_date": {
                            "anyOf": [{"type": "string"}, {"type": "null"}],
                            "description": "ISO date extracted from text (YYYY-MM-DD or YYYY-MM-DDTHH:MM), or null if no date mentioned",
                        },
                    },
                    "required": ["event_type", "summary", "confidence"],
                    "additionalProperties": False,
                },
                {"type": "null"},
            ]
        }
    },
    "required": ["event"],
    "additionalProperties": False,
}


def parse_args() -> tuple[int | None, int | None, bool, int, int, str | None]:
    candidates_only = False
    worker_id = 0
    worker_total = 1
    model_override = None

    if "--candidates-only" in sys.argv:
        candidates_only = True
        sys.argv.remove("--candidates-only")

    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        try:
            model_override = sys.argv[idx + 1]
        except IndexError:
            raise ValueError("--model expects a model name")
        sys.argv.pop(idx + 1)
        sys.argv.pop(idx)

    # --worker 2/6 means "I am worker 2 of 6"
    if "--worker" in sys.argv:
        idx = sys.argv.index("--worker")
        try:
            parts = sys.argv[idx + 1].split("/")
            worker_id = int(parts[0])
            worker_total = int(parts[1])
        except (IndexError, ValueError):
            raise ValueError("--worker expects format N/M, e.g. --worker 0/6")
        sys.argv.pop(idx + 1)
        sys.argv.pop(idx)

    if len(sys.argv) >= 3 and sys.argv[1] == "--chunk-id":
        try:
            chunk_id = int(sys.argv[2])
        except ValueError:
            raise ValueError(f"Invalid chunk_id: {sys.argv[2]}")
        return None, chunk_id, candidates_only, worker_id, worker_total, model_override

    if len(sys.argv) >= 2:
        try:
            value = int(sys.argv[1])
        except ValueError:
            raise ValueError(f"Invalid limit: {sys.argv[1]}")
        if value <= 0:
            raise ValueError(f"Limit must be > 0, got: {value}")
        return value, None, candidates_only, worker_id, worker_total, model_override

    return DEFAULT_LIMIT, None, candidates_only, worker_id, worker_total, model_override


def _rows_to_chunk_dicts(rows: list[tuple]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        result.append(
            {
                "chunk_id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "timestamp_start": str(row[3]) if row[3] else "",
                "text": row[4],
            }
        )
    return result


MIN_TEXT_LENGTH = 50


def fetch_candidate_chunks(
    limit: int,
    candidates_only: bool = False,
    worker_id: int = 0,
    worker_total: int = 1,
) -> list[dict[str, Any]]:
    partition_clause = ""
    if worker_total > 1:
        partition_clause = f"AND c.id %% {worker_total} = {worker_id}"

    if candidates_only:
        sql = f"""
        SELECT c.id, c.document_id, c.chunk_index, c.timestamp_start, c.text
        FROM chunks c
        JOIN event_candidate_chunks ecc ON ecc.chunk_id = c.id
        LEFT JOIN events e ON e.chunk_id = c.id
        LEFT JOIN chunks_event_checked cec ON cec.chunk_id = c.id
        WHERE e.id IS NULL AND cec.chunk_id IS NULL
          AND length(c.text) >= {MIN_TEXT_LENGTH}
          {partition_clause}
        ORDER BY ecc.priority DESC, c.id
        LIMIT %s
        """
    else:
        sql = f"""
        SELECT c.id, c.document_id, c.chunk_index, c.timestamp_start, c.text
        FROM chunks c
        LEFT JOIN events e ON e.chunk_id = c.id
        LEFT JOIN chunks_event_checked cec ON cec.chunk_id = c.id
        WHERE e.id IS NULL AND cec.chunk_id IS NULL
          AND length(c.text) >= {MIN_TEXT_LENGTH}
          {partition_clause}
        ORDER BY c.id
        LIMIT %s
        """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()
    return _rows_to_chunk_dicts(rows)


def fetch_chunk_by_id(chunk_id: int) -> list[dict[str, Any]]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, document_id, chunk_index, timestamp_start, text FROM chunks WHERE id = %s LIMIT 1",
                (chunk_id,),
            )
            rows = cur.fetchall()
    return _rows_to_chunk_dicts(rows)


def normalize_event(raw_event: dict[str, Any] | None, fallback_text: str) -> dict[str, Any] | None:
    if raw_event is None or not isinstance(raw_event, dict):
        return None

    event_type = str(raw_event.get("event_type", "")).strip().lower()
    summary = str(raw_event.get("summary", "")).strip()

    try:
        confidence = float(raw_event.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(0.0, min(confidence, 1.0))

    if event_type not in EVENT_TYPES:
        return None

    if not summary:
        summary = fallback_text[:220].strip()

    if not summary:
        return None

    # Extract LLM-provided date (if present and valid)
    event_date = raw_event.get("event_date")
    if event_date and isinstance(event_date, str):
        event_date = event_date.strip()
        # Basic validation: must look like a date
        if len(event_date) < 8 or not event_date[:4].isdigit():
            event_date = None
    else:
        event_date = None

    return {
        "event_type": event_type,
        "summary": summary[:500],
        "confidence": confidence,
        "event_date": event_date,
    }


def detect_event_with_llm(llm: LLMExtractionClient, text: str) -> dict[str, Any] | None:
    payload = f"Chunk text:\n{text[:6000]}"

    parsed = llm.extract_object(
        system_prompt=EVENT_SYSTEM_PROMPT,
        user_payload=payload,
        tool_name="return_event",
        tool_description="Return one timeline-worthy event or null",
        input_schema=EVENT_TOOL_SCHEMA,
    )

    return normalize_event(parsed.get("event"), fallback_text=text)


def insert_event(document_id: int, chunk_id: int, event_type: str, event_time: str | None, summary: str, confidence: float) -> int:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (document_id, chunk_id, event_type, event_time, summary, confidence, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING id
                """,
                (document_id, chunk_id, event_type, event_time, summary, confidence),
            )
            rows = cur.fetchall()
        conn.commit()
    return rows[0][0]


def fetch_chunk_entity_ids(chunk_id: int) -> list[int]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT entity_id FROM chunk_entities WHERE chunk_id = %s ORDER BY id LIMIT 3",
                (chunk_id,),
            )
            rows = cur.fetchall()
    return [row[0] for row in rows]


def insert_event_entity(event_id: int, entity_id: int, role: str = "mentioned") -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO event_entities (event_id, entity_id, role, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (event_id, entity_id, COALESCE(role, ''))
                DO NOTHING
                """,
                (event_id, entity_id, role),
            )
        conn.commit()


def mark_event_checked(chunk_id: int) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chunks_event_checked (chunk_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (chunk_id,),
            )
        conn.commit()


def _create_extraction_run(module: str, model: str, worker_id: int, worker_total: int, batch_size: int) -> int | None:
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO extraction_runs (module, model, worker_id, worker_total, batch_size)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (module, model, worker_id, worker_total, batch_size),
                )
                run_id = cur.fetchall()[0][0]
            conn.commit()
        return run_id
    except Exception:
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
    except Exception:
        pass


def main() -> None:
    limit, chunk_id, candidates_only, worker_id, worker_total, model_override = parse_args()
    llm = LLMExtractionClient(model_override=model_override, module="extraction.events")

    run_id = None

    if chunk_id is not None:
        rows = fetch_chunk_by_id(chunk_id)
        print(f"Testing single chunk_id={chunk_id}. Found rows: {len(rows)}")
    else:
        rows = fetch_candidate_chunks(
            limit=limit or DEFAULT_LIMIT,
            candidates_only=candidates_only,
            worker_id=worker_id,
            worker_total=worker_total,
        )
        print(f"Chunks to process: {len(rows)} (worker {worker_id}/{worker_total})")
        run_id = _create_extraction_run(
            "events", llm.model, worker_id, worker_total, limit or DEFAULT_LIMIT
        )

    processed = 0
    events_written = 0
    event_entities_written = 0

    for row in rows:
        if _shutdown_requested:
            print(f"[SHUTDOWN] Stopping after {processed} chunks.")
            break

        current_chunk_id = row["chunk_id"]
        document_id = row["document_id"]
        text = row["text"] or ""
        timestamp_start = row["timestamp_start"] or None

        detected = detect_event_with_llm(llm, text)

        print(
            json.dumps(
                {
                    "chunk_id": current_chunk_id,
                    "event_detected": bool(detected),
                    "event_type": None if not detected else detected["event_type"],
                },
                ensure_ascii=False,
            )
        )

        if detected:
            # Prefer LLM-extracted date, fallback to chunk timestamp
            event_time = detected.get("event_date") or timestamp_start
            event_id = insert_event(
                document_id=document_id,
                chunk_id=current_chunk_id,
                event_type=detected["event_type"],
                event_time=event_time,
                summary=detected["summary"],
                confidence=float(detected["confidence"]),
            )
            events_written += 1

            entity_ids = fetch_chunk_entity_ids(current_chunk_id)
            for entity_id in entity_ids:
                insert_event_entity(event_id=event_id, entity_id=entity_id, role="mentioned")
                event_entities_written += 1
        else:
            mark_event_checked(current_chunk_id)

        processed += 1

    _finish_extraction_run(run_id, processed, events_written, processed - events_written)

    print(
        json.dumps(
            {
                "processed_chunks": processed,
                "events_written": events_written,
                "event_entities_written": event_entities_written,
                "extraction_run_id": run_id,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
