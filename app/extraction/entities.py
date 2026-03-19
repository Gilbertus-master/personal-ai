import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.extraction.taxonomy import ENTITY_TYPES
from app.ingestion.common.db import _run_sql, _run_sql_all_lines


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


DEFAULT_LIMIT = 50


def sql_escape(value: str) -> str:
    return value.replace("'", "''")


def parse_limit() -> int:
    if len(sys.argv) >= 2:
        try:
            value = int(sys.argv[1])
        except ValueError:
            raise ValueError(f"Invalid limit: {sys.argv[1]}")
        if value <= 0:
            raise ValueError(f"Limit must be > 0, got: {value}")
        return value
    return DEFAULT_LIMIT


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
    lines = _run_sql_all_lines(sql)
    if not lines:
        return []

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


def call_entity_extractor(text: str) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []

    lowered = text.lower()

    heuristic_topics = [
        "trading",
        "zosia",
        "asd",
        "autyzm",
        "gilbertus",
        "respect energy",
        "polanica",
        "warszawa",
    ]

    for item in heuristic_topics:
        if item in lowered:
            if item == "zosia":
                entities.append(
                    {
                        "name": "Zosia",
                        "canonical_name": "Zosia",
                        "entity_type": "person",
                        "mention_text": "Zosia",
                        "confidence": 0.70,
                    }
                )
            elif item == "respect energy":
                entities.append(
                    {
                        "name": "Respect Energy",
                        "canonical_name": "Respect Energy",
                        "entity_type": "company",
                        "mention_text": "Respect Energy",
                        "confidence": 0.70,
                    }
                )
            elif item == "gilbertus":
                entities.append(
                    {
                        "name": "Gilbertus Albans",
                        "canonical_name": "Gilbertus Albans",
                        "entity_type": "project",
                        "mention_text": "Gilbertus",
                        "confidence": 0.65,
                    }
                )
            elif item in {"polanica", "warszawa"}:
                entities.append(
                    {
                        "name": item.title(),
                        "canonical_name": item.title(),
                        "entity_type": "location",
                        "mention_text": item.title(),
                        "confidence": 0.65,
                    }
                )
            else:
                entities.append(
                    {
                        "name": item,
                        "canonical_name": item,
                        "entity_type": "topic",
                        "mention_text": item,
                        "confidence": 0.60,
                    }
                )

    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for entity in entities:
        key = (entity["canonical_name"], entity["entity_type"])
        if key not in dedup:
            dedup[key] = entity

    return list(dedup.values())


def upsert_entity(entity: dict[str, Any]) -> int:
    canonical_name = sql_escape(entity["canonical_name"])
    name = sql_escape(entity["name"])
    entity_type = sql_escape(entity["entity_type"])

    sql = f"""
    INSERT INTO entities (name, entity_type, canonical_name, created_at)
    VALUES ('{name}', '{entity_type}', '{canonical_name}', NOW())
    ON CONFLICT ((COALESCE(canonical_name, name)), entity_type)
    DO UPDATE SET
        name = EXCLUDED.name
    RETURNING id;
    """
    output = _run_sql(sql).strip()
    return int(output.splitlines()[-1])


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
    limit = parse_limit()
    rows = fetch_candidate_chunks(limit=limit)

    print(f"Chunks to process: {len(rows)}")

    processed = 0
    mentions_written = 0

    for row in rows:
        chunk_id = row["chunk_id"]
        text = row["text"] or ""

        entities = call_entity_extractor(text)

        print(
            json.dumps(
                {
                    "chunk_id": chunk_id,
                    "entity_count": len(entities),
                },
                ensure_ascii=False,
            )
        )

        for entity in entities:
            if entity["entity_type"] not in ENTITY_TYPES:
                continue

            entity_id = upsert_entity(entity)
            insert_chunk_entity(
                chunk_id=chunk_id,
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
