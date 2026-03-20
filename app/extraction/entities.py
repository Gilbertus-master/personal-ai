import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.extraction.llm_client import LLMExtractionClient
from app.extraction.taxonomy import ENTITY_TYPES
from app.ingestion.common.db import _run_sql, _run_sql_all_lines


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
- Prefer entities central to the meaning of the chunk.
- Exclude boilerplate metadata, email header clutter, recipient lists, signatures, and incidental mentions unless they are clearly central to the chunk’s meaning.
- For long email threads, focus on the main actors or organizations relevant to the core content, not every person copied on the thread.
- Return at most 5 entities.
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


def sql_escape(value: str) -> str:
    return value.replace("'", "''")


def parse_args() -> tuple[int | None, int | None]:
    if len(sys.argv) >= 3 and sys.argv[1] == "--chunk-id":
        try:
            chunk_id = int(sys.argv[2])
        except ValueError:
            raise ValueError(f"Invalid chunk_id: {sys.argv[2]}")
        return None, chunk_id

    if len(sys.argv) >= 2:
        try:
            value = int(sys.argv[1])
        except ValueError:
            raise ValueError(f"Invalid limit: {sys.argv[1]}")
        if value <= 0:
            raise ValueError(f"Limit must be > 0, got: {value}")
        return value, None

    return DEFAULT_LIMIT, None


def parse_chunk_rows(lines: list[str]) -> list[dict[str, Any]]:
    rows = []
    for line in lines:
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        rows.append(
            {
                "chunk_id": int(parts[0]),
                "document_id": int(parts[1]),
                "chunk_index": int(parts[2]),
                "text": parts[3],
            }
        )
    return rows


def fetch_candidate_chunks(limit: int) -> list[dict[str, Any]]:
    sql = f"""
    SELECT concat_ws(
        E'\t',
        c.id::text,
        c.document_id::text,
        c.chunk_index::text,
        replace(replace(c.text, E'\t', ' '), E'\n', ' ')
    )
    FROM chunks c
    LEFT JOIN chunk_entities ce ON ce.chunk_id = c.id
    WHERE ce.id IS NULL
    ORDER BY c.id
    LIMIT {limit};
    """
    return parse_chunk_rows(_run_sql_all_lines(sql))


def fetch_chunk_by_id(chunk_id: int) -> list[dict[str, Any]]:
    sql = f"""
    SELECT concat_ws(
        E'\t',
        c.id::text,
        c.document_id::text,
        c.chunk_index::text,
        replace(replace(c.text, E'\t', ' '), E'\n', ' ')
    )
    FROM chunks c
    WHERE c.id = {chunk_id}
    LIMIT 1;
    """
    return parse_chunk_rows(_run_sql_all_lines(sql))


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
    canonical_name = sql_escape(entity["canonical_name"])
    name = sql_escape(entity["name"])
    entity_type = sql_escape(entity["entity_type"])

    lookup_sql = f"""
    SELECT id::text
    FROM entities
    WHERE entity_type = '{entity_type}'
      AND (
        canonical_name = '{canonical_name}'
        OR name = '{name}'
        OR name = '{canonical_name}'
        OR canonical_name = '{name}'
      )
    ORDER BY id
    LIMIT 1;
    """
    existing = _run_sql_all_lines(lookup_sql)
    if existing:
        return int(existing[0])

    insert_sql = f"""
    INSERT INTO entities (name, entity_type, canonical_name, created_at)
    VALUES ('{name}', '{entity_type}', '{canonical_name}', NOW())
    ON CONFLICT (name, entity_type)
    DO UPDATE SET
        canonical_name = COALESCE(entities.canonical_name, EXCLUDED.canonical_name)
    RETURNING id;
    """
    return int(_run_sql(insert_sql).strip())


def insert_chunk_entity(chunk_id: int, entity_id: int, mention_text: str, confidence: float) -> None:
    mention_sql = sql_escape(mention_text)
    sql = f"""
    INSERT INTO chunk_entities (chunk_id, entity_id, mention_text, confidence, created_at)
    VALUES ({chunk_id}, {entity_id}, '{mention_sql}', {confidence}, NOW())
    ON CONFLICT (chunk_id, entity_id, COALESCE(mention_text, ''))
    DO NOTHING;
    """
    _run_sql(sql, expect_rows=False)


def main() -> None:
    limit, chunk_id = parse_args()
    llm = LLMExtractionClient()

    if chunk_id is not None:
        rows = fetch_chunk_by_id(chunk_id)
        print(f"Testing single chunk_id={chunk_id}. Found rows: {len(rows)}")
    else:
        rows = fetch_candidate_chunks(limit=limit or DEFAULT_LIMIT)
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
