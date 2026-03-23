import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.extraction.llm_client import LLMExtractionClient
from app.extraction.taxonomy import EVENT_TYPES
from app.db.postgres import get_pg_connection


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


DEFAULT_LIMIT = 50


EVENT_SYSTEM_PROMPT = """
You extract one timeline-worthy event from a chunk of text.

Rules:
- Return an event only if the chunk describes a concrete real-world occurrence, decision, conflict, support act, meeting, trade, health development, or family-relevant occurrence.
- Do NOT return events for generic advice, abstract discussion, educational explanations, definitions, broad analysis, or recommendations.
- Prefer real events affecting the user or closely related people over general informational content.
- Use only these event_type values:
  conflict, support, decision, meeting, trade, health, family
- If the chunk is not event-worthy, return event = null.
- confidence must be between 0 and 1.
- summary must be short, factual, and in the language of the chunk.
- Be conservative.
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
                            "enum": ["conflict", "support", "decision", "meeting", "trade", "health", "family"],
                        },
                        "summary": {"type": "string"},
                        "confidence": {"type": "number"},
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


def parse_args() -> tuple[int | None, int | None, bool]:
    candidates_only = False

    if "--candidates-only" in sys.argv:
        candidates_only = True
        sys.argv.remove("--candidates-only")

    if len(sys.argv) >= 3 and sys.argv[1] == "--chunk-id":
        try:
            chunk_id = int(sys.argv[2])
        except ValueError:
            raise ValueError(f"Invalid chunk_id: {sys.argv[2]}")
        return None, chunk_id, candidates_only

    if len(sys.argv) >= 2:
        try:
            value = int(sys.argv[1])
        except ValueError:
            raise ValueError(f"Invalid limit: {sys.argv[1]}")
        if value <= 0:
            raise ValueError(f"Limit must be > 0, got: {value}")
        return value, None, candidates_only

    return DEFAULT_LIMIT, None, candidates_only


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


def fetch_candidate_chunks(limit: int, candidates_only: bool = False) -> list[dict[str, Any]]:
    if candidates_only:
        sql = """
        SELECT c.id, c.document_id, c.chunk_index, c.timestamp_start, c.text
        FROM chunks c
        JOIN event_candidate_chunks ecc ON ecc.chunk_id = c.id
        LEFT JOIN events e ON e.chunk_id = c.id
        WHERE e.id IS NULL
        ORDER BY ecc.priority DESC, c.id
        LIMIT %s
        """
    else:
        sql = """
        SELECT c.id, c.document_id, c.chunk_index, c.timestamp_start, c.text
        FROM chunks c
        LEFT JOIN events e ON e.chunk_id = c.id
        WHERE e.id IS NULL
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

    return {
        "event_type": event_type,
        "summary": summary[:500],
        "confidence": confidence,
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


def main() -> None:
    limit, chunk_id, candidates_only = parse_args()
    llm = LLMExtractionClient()

    if chunk_id is not None:
        rows = fetch_chunk_by_id(chunk_id)
        print(f"Testing single chunk_id={chunk_id}. Found rows: {len(rows)}")
    else:
        rows = fetch_candidate_chunks(limit=limit or DEFAULT_LIMIT, candidates_only=candidates_only)
        print(f"Chunks to process: {len(rows)}")

    processed = 0
    events_written = 0
    event_entities_written = 0

    for row in rows:
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
            event_id = insert_event(
                document_id=document_id,
                chunk_id=current_chunk_id,
                event_type=detected["event_type"],
                event_time=timestamp_start,
                summary=detected["summary"],
                confidence=float(detected["confidence"]),
            )
            events_written += 1

            entity_ids = fetch_chunk_entity_ids(current_chunk_id)
            for entity_id in entity_ids:
                insert_event_entity(event_id=event_id, entity_id=entity_id, role="mentioned")
                event_entities_written += 1

        processed += 1

    print(
        json.dumps(
            {
                "processed_chunks": processed,
                "events_written": events_written,
                "event_entities_written": event_entities_written,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
