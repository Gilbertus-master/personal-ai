import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.extraction.llm_client import LLMExtractionClient
from app.extraction.taxonomy import ENTITY_TYPES
from app.db.postgres import get_pg_connection


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
- Be conservative.
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


def parse_args() -> tuple[int | None, int | None, bool, bool]:
    candidates_only = False
    event_backfill_only = False

    if "--candidates-only" in sys.argv:
        candidates_only = True
        sys.argv.remove("--candidates-only")

    if "--event-backfill-only" in sys.argv:
        event_backfill_only = True
        sys.argv.remove("--event-backfill-only")

    if len(sys.argv) >= 3 and sys.argv[1] == "--chunk-id":
        try:
            chunk_id = int(sys.argv[2])
        except ValueError:
            raise ValueError(f"Invalid chunk_id: {sys.argv[2]}")
        return None, chunk_id, candidates_only, event_backfill_only

    if len(sys.argv) >= 2:
        try:
            value = int(sys.argv[1])
        except ValueError:
            raise ValueError(f"Invalid limit: {sys.argv[1]}")
        if value <= 0:
            raise ValueError(f"Limit must be > 0, got: {value}")
        return value, None, candidates_only, event_backfill_only

    return DEFAULT_LIMIT, None, candidates_only, event_backfill_only


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


def fetch_candidate_chunks(
    limit: int,
    candidates_only: bool = False,
    event_backfill_only: bool = False,
) -> list[dict[str, Any]]:
    if event_backfill_only:
        sql = """
        SELECT c.id, c.document_id, c.chunk_index, c.text
        FROM chunks c
        JOIN event_entity_backfill_candidates ebc ON ebc.chunk_id = c.id
        LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
        WHERE ce.id IS NULL
        ORDER BY c.id
        LIMIT %s
        """
    elif candidates_only:
        sql = """
        SELECT c.id, c.document_id, c.chunk_index, c.text
        FROM chunks c
        JOIN event_candidate_chunks ecc ON ecc.chunk_id = c.id
        LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
        WHERE ce.id IS NULL
        ORDER BY ecc.priority DESC, c.id
        LIMIT %s
        """
    else:
        sql = """
        SELECT c.id, c.document_id, c.chunk_index, c.text
        FROM chunks c
        LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
        WHERE ce.id IS NULL
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
            cur.execute(
                """
                SELECT id FROM entities
                WHERE entity_type = %s
                  AND (canonical_name = %s OR name = %s OR name = %s OR canonical_name = %s)
                ORDER BY id LIMIT 1
                """,
                (entity_type, canonical_name, name, canonical_name, name),
            )
            rows = cur.fetchall()
            if rows:
                return rows[0][0]

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


def main() -> None:
    limit, chunk_id, candidates_only, event_backfill_only = parse_args()
    llm = LLMExtractionClient()

    if chunk_id is not None:
        rows = fetch_chunk_by_id(chunk_id)
        print(f"Testing single chunk_id={chunk_id}. Found rows: {len(rows)}")
    else:
        rows = fetch_candidate_chunks(
            limit=limit or DEFAULT_LIMIT,
            candidates_only=candidates_only,
            event_backfill_only=event_backfill_only,
        )
        print(f"Chunks to process: {len(rows)}")

    processed = 0
    mentions_written = 0

    for row in rows:
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

        for entity in entities:
            entity_id = upsert_entity(entity)
            insert_chunk_entity(
                chunk_id=current_chunk_id,
                entity_id=entity_id,
                mention_text=entity["mention_text"],
                confidence=float(entity["confidence"]),
            )
            mentions_written += 1

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
