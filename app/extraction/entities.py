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
    return parse_chunk_rows(lines)


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
    lines = _run_sql_all_lines(sql)
    return parse_chunk_rows(lines)


def call_entity_extractor(text: str) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    lowered = text.lower()

    rules = [
        ("Sebastian", "Sebastian", "person", ["sebastian"]),
        ("Zosia", "Zosia", "person", ["zosia"]),
        ("Ewa", "Ewa", "person", ["ewa"]),
        ("Wojtek", "Wojtek", "person", ["wojtek"]),
        ("Adaś", "Adaś", "person", ["adaś", "adais"]),
        ("Respect Energy", "Respect Energy", "company", ["respect energy"]),
        ("Jet Story", "Jet Story", "company", ["jet story"]),
        ("Gilbertus Albans", "Gilbertus Albans", "project", ["gilbertus"]),
        ("trading", "trading", "topic", ["trading"]),
        ("autyzm", "autyzm", "topic", ["autyzm", "asperger", "asd"]),
        ("konflikt", "konflikt", "topic", ["konflikt", "silent treatment", "kłótn", "spór"]),
        ("Warszawa", "Warszawa", "location", ["warszawa"]),
        ("Polanica", "Polanica", "location", ["polanica"]),
    ]

    for name, canonical_name, entity_type, markers in rules:
        for marker in markers:
            if marker in lowered:
                entities.append(
                    {
                        "name": name,
                        "canonical_name": canonical_name,
                        "entity_type": entity_type,
                        "mention_text": marker,
                        "confidence": 0.70,
                    }
                )
                break

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
    limit, chunk_id = parse_args()

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

        entities = call_entity_extractor(text)

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
            if entity["entity_type"] not in ENTITY_TYPES:
                continue

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
