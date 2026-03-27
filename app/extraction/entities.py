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
from app.extraction.taxonomy import ENTITY_TYPES  # noqa: E402
from app.db.postgres import get_pg_connection  # noqa: E402


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


DEFAULT_LIMIT = 50


ENTITY_SYSTEM_PROMPT = """
You extract only the most relevant explicit entities from a chunk of text.

Rules:
- Return only entities explicitly present in the chunk.
- Do not infer hidden entities.
- Do not invent canonical names beyond light normalization of the visible mention.
- Use only these entity_type values:
  person, company, project, topic, location
- Prefer entities central to the main meaning of the chunk.
- Exclude incidental mentions, side references, generic background context, and weakly related entities.
- Exclude entities that appear only in quoted context unless they are central to the chunk's main point.
- Exclude boilerplate metadata, email header clutter, recipient lists, signatures, and copied thread noise unless clearly central.
- For medical or psychological chunks, prefer the diagnosis/condition/topic over unrelated organizations or side people.
- For relational chunks, include only the people central to the actual situation described.
- Return at most 4 entities.
- If nothing clearly relevant is present, return an empty list.
- mention_text must be a short explicit surface form from the chunk.
- confidence must be between 0 and 1.
""".strip()


ENTITY_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "canonical_name": {"type": "string"},
                    "entity_type": {
                        "type": "string",
                        "enum": ["person", "company", "project", "topic", "location"],
                    },
                    "mention_text": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["name", "canonical_name", "entity_type", "mention_text", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["entities"],
    "additionalProperties": False,
}


def parse_args() -> tuple[int | None, int | None, bool, bool, int, int, str | None]:
    candidates_only = False
    event_backfill_only = False
    worker_id = 0
    worker_total = 1
    model_override = None

    if "--candidates-only" in sys.argv:
        candidates_only = True
        sys.argv.remove("--candidates-only")

    if "--event-backfill-only" in sys.argv:
        event_backfill_only = True
        sys.argv.remove("--event-backfill-only")

    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        try:
            model_override = sys.argv[idx + 1]
        except IndexError:
            raise ValueError("--model expects a model name")
        sys.argv.pop(idx + 1)
        sys.argv.pop(idx)

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
        return None, chunk_id, candidates_only, event_backfill_only, worker_id, worker_total, model_override

    if len(sys.argv) >= 2:
        try:
            value = int(sys.argv[1])
        except ValueError:
            raise ValueError(f"Invalid limit: {sys.argv[1]}")
        if value <= 0:
            raise ValueError(f"Limit must be > 0, got: {value}")
        return value, None, candidates_only, event_backfill_only, worker_id, worker_total, model_override

    return DEFAULT_LIMIT, None, candidates_only, event_backfill_only, worker_id, worker_total, model_override


def _rows_to_chunk_dicts(rows: list[tuple]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        result.append(
            {
                "chunk_id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "text": row[3],
            }
        )
    return result


MIN_TEXT_LENGTH = 50


def fetch_candidate_chunks(
    limit: int,
    candidates_only: bool = False,
    event_backfill_only: bool = False,
    worker_id: int = 0,
    worker_total: int = 1,
) -> list[dict[str, Any]]:
    partition_clause = ""
    if worker_total > 1:
        partition_clause = f"AND c.id %% {worker_total} = {worker_id}"

    if event_backfill_only:
        sql = f"""
        SELECT c.id, c.document_id, c.chunk_index, c.text
        FROM chunks c
        JOIN event_entity_backfill_candidates ebc ON ebc.chunk_id = c.id
        LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
        LEFT JOIN chunks_entity_checked cec ON cec.chunk_id = c.id
        WHERE ce.id IS NULL AND cec.chunk_id IS NULL
          AND length(c.text) >= {MIN_TEXT_LENGTH}
          {partition_clause}
        ORDER BY c.id
        LIMIT %s
        """
    elif candidates_only:
        sql = f"""
        SELECT c.id, c.document_id, c.chunk_index, c.text
        FROM chunks c
        JOIN event_candidate_chunks ecc ON ecc.chunk_id = c.id
        LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
        LEFT JOIN chunks_entity_checked cec ON cec.chunk_id = c.id
        WHERE ce.id IS NULL AND cec.chunk_id IS NULL
          AND length(c.text) >= {MIN_TEXT_LENGTH}
          {partition_clause}
        ORDER BY ecc.priority DESC, c.id
        LIMIT %s
        """
    else:
        sql = f"""
        SELECT c.id, c.document_id, c.chunk_index, c.text
        FROM chunks c
        LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
        LEFT JOIN chunks_entity_checked cec ON cec.chunk_id = c.id
        WHERE ce.id IS NULL AND cec.chunk_id IS NULL
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
                "SELECT id, document_id, chunk_index, text FROM chunks WHERE id = %s LIMIT 1",
                (chunk_id,),
            )
            rows = cur.fetchall()
    return _rows_to_chunk_dicts(rows)


def normalize_entity(entity: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(entity, dict):
        return None

    name = str(entity.get("name", "")).strip()
    canonical_name = str(entity.get("canonical_name", "")).strip()
    entity_type = str(entity.get("entity_type", "")).strip().lower()
    mention_text = str(entity.get("mention_text", "")).strip()

    try:
        confidence = float(entity.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(0.0, min(confidence, 1.0))

    if not name or not canonical_name or not mention_text:
        return None
    if entity_type not in ENTITY_TYPES:
        return None

    return {
        "name": name,
        "canonical_name": canonical_name,
        "entity_type": entity_type,
        "mention_text": mention_text,
        "confidence": confidence,
    }


def extract_entities_from_text(llm: LLMExtractionClient, text: str) -> list[dict[str, Any]]:
    payload = f"Chunk text:\n{text[:6000]}"

    parsed = llm.extract_object(
        system_prompt=ENTITY_SYSTEM_PROMPT,
        user_payload=payload,
        tool_name="return_entities",
        tool_description="Return explicit entities found in the chunk",
        input_schema=ENTITY_TOOL_SCHEMA,
    )

    raw_entities = parsed.get("entities", [])
    if not isinstance(raw_entities, list):
        return []

    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in raw_entities:
        normalized = normalize_entity(item)
        if not normalized:
            continue

        key = (normalized["canonical_name"], normalized["entity_type"])
        if key in seen:
            continue

        seen.add(key)
        result.append(normalized)

    return result


def upsert_entity(entity: dict[str, Any]) -> int:
    canonical_name = entity["canonical_name"]
    name = entity["name"]
    entity_type = entity["entity_type"]

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # 1. Exact match (case-insensitive)
            cur.execute(
                """
                SELECT id FROM entities
                WHERE entity_type = %s
                  AND (LOWER(TRIM(canonical_name)) = LOWER(TRIM(%s))
                       OR LOWER(TRIM(name)) = LOWER(TRIM(%s))
                       OR LOWER(TRIM(name)) = LOWER(TRIM(%s))
                       OR LOWER(TRIM(canonical_name)) = LOWER(TRIM(%s)))
                ORDER BY id LIMIT 1
                """,
                (entity_type, canonical_name, name, canonical_name, name),
            )
            rows = cur.fetchall()
            if rows:
                return rows[0][0]

            # 2. Fuzzy match (trigram similarity > 0.7, same type)
            cur.execute(
                """
                SELECT id FROM entities
                WHERE entity_type = %s
                  AND canonical_name %% %s
                  AND similarity(canonical_name, %s) > 0.7
                ORDER BY similarity(canonical_name, %s) DESC, id
                LIMIT 1
                """,
                (entity_type, canonical_name, canonical_name, canonical_name),
            )
            rows = cur.fetchall()
            if rows:
                return rows[0][0]

            # 3. Insert new
            cur.execute(
                """
                INSERT INTO entities (name, entity_type, canonical_name, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (name, entity_type)
                DO UPDATE SET canonical_name = COALESCE(entities.canonical_name, EXCLUDED.canonical_name)
                RETURNING id
                """,
                (name, entity_type, canonical_name),
            )
            rows = cur.fetchall()
        conn.commit()
    return rows[0][0]


def insert_chunk_entity(chunk_id: int, entity_id: int, mention_text: str, confidence: float) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chunk_entities (chunk_id, entity_id, mention_text, confidence, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (chunk_id, entity_id, COALESCE(mention_text, ''))
                DO NOTHING
                """,
                (chunk_id, entity_id, mention_text, confidence),
            )
        conn.commit()


def mark_entity_checked(chunk_id: int) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chunks_entity_checked (chunk_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (chunk_id,),
            )
        conn.commit()


def main() -> None:
    limit, chunk_id, candidates_only, event_backfill_only, worker_id, worker_total, model_override = parse_args()
    llm = LLMExtractionClient(model_override=model_override)

    if chunk_id is not None:
        rows = fetch_chunk_by_id(chunk_id)
        print(f"Testing single chunk_id={chunk_id}. Found rows: {len(rows)}")
    else:
        rows = fetch_candidate_chunks(
            limit=limit or DEFAULT_LIMIT,
            candidates_only=candidates_only,
            event_backfill_only=event_backfill_only,
            worker_id=worker_id,
            worker_total=worker_total,
        )
        print(f"Chunks to process: {len(rows)} (worker {worker_id}/{worker_total})")

    processed = 0
    mentions_written = 0

    for row in rows:
        if _shutdown_requested:
            print(f"[SHUTDOWN] Stopping after {processed} chunks.")
            break

        current_chunk_id = row["chunk_id"]
        text = row["text"] or ""

        entities = extract_entities_from_text(llm, text)

        print(
            json.dumps(
                {
                    "chunk_id": current_chunk_id,
                    "entity_count": len(entities),
                    "entity_names": [e["canonical_name"] for e in entities],
                },
                ensure_ascii=False,
            )
        )

        if entities:
            for entity in entities:
                entity_id = upsert_entity(entity)
                insert_chunk_entity(
                    chunk_id=current_chunk_id,
                    entity_id=entity_id,
                    mention_text=entity["mention_text"],
                    confidence=float(entity["confidence"]),
                )
                mentions_written += 1
        else:
            mark_entity_checked(current_chunk_id)

        processed += 1

    print(
        json.dumps(
            {
                "processed_chunks": processed,
                "mentions_written": mentions_written,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
