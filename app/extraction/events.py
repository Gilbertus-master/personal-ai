import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.extraction.taxonomy import EVENT_TYPES
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
        COALESCE(c.timestamp_start::text, ''),
        replace(replace(c.text, E'\t', ' '), E'\n', ' ')
    )
    FROM chunks c
    LEFT JOIN events e ON e.chunk_id = c.id
    WHERE e.id IS NULL
    ORDER BY c.id
    LIMIT {limit};
    """
    lines = _run_sql_all_lines(sql)
    if not lines:
        return []

    rows = []
    for line in lines:
        parts = line.split("\t", 4)
        if len(parts) != 5:
            continue
        rows.append(
            {
                "chunk_id": int(parts[0]),
                "document_id": int(parts[1]),
                "chunk_index": int(parts[2]),
                "timestamp_start": parts[3],
                "text": parts[4],
            }
        )
    return rows


def detect_event(text: str) -> dict[str, Any] | None:
    lowered = text.lower()

    rules = [
        ("conflict", ["konflikt", "kłótn", "spór", "silent treatment"]),
        ("support", ["wsparcie", "pomoc", "pomóc", "przyjecha"]),
        ("decision", ["decyzj", "zdecydowa", "rozważam", "postanowi"]),
        ("meeting", ["spotkani", "sesja", "call", "rozmow"]),
        ("trade", ["trading", "pozycj", "rynek", "transakcj"]),
        ("health", ["chorob", "diagnoz", "asd", "autyzm"]),
        ("family", ["syn", "dzieci", "mama", "tata", "zosia"]),
        ("milestone", ["założy", "powsta", "ukończy", "kupiłe", "kupił"]),
    ]

    for event_type, markers in rules:
        for marker in markers:
            if marker in lowered:
                summary = text[:220].strip()
                if not summary:
                    summary = f"Detected {event_type} event"
                return {
                    "event_type": event_type,
                    "summary": summary,
                    "confidence": 0.60,
                }

    return None


def insert_event(document_id: int, chunk_id: int, event_type: str, event_time: str | None, summary: str, confidence: float) -> int:
    event_time_sql = "NULL" if not event_time else f"'{sql_escape(event_time)}'"
    summary_sql = sql_escape(summary)
    event_type_sql = sql_escape(event_type)

    sql = f"""
    INSERT INTO events (document_id, chunk_id, event_type, event_time, summary, confidence, created_at)
    VALUES ({document_id}, {chunk_id}, '{event_type_sql}', {event_time_sql}, '{summary_sql}', {confidence}, NOW())
    RETURNING id;
    """
    return int(_run_sql(sql).strip())


def fetch_chunk_entity_ids(chunk_id: int) -> list[int]:
    sql = f"""
    SELECT entity_id::text
    FROM chunk_entities
    WHERE chunk_id = {chunk_id}
    ORDER BY entity_id;
    """
    lines = _run_sql_all_lines(sql)
    return [int(line) for line in lines if line.strip()]


def insert_event_entity(event_id: int, entity_id: int, role: str = "mentioned") -> None:
    role_sql = sql_escape(role)
    sql = f"""
    INSERT INTO event_entities (event_id, entity_id, role, created_at)
    VALUES ({event_id}, {entity_id}, '{role_sql}', NOW())
    ON CONFLICT (event_id, entity_id, COALESCE(role, ''))
    DO NOTHING;
    """
    _run_sql(sql, expect_rows=False)


def main() -> None:
    limit = parse_limit()
    rows = fetch_candidate_chunks(limit=limit)

    print(f"Chunks to process: {len(rows)}")

    processed = 0
    events_written = 0
    event_entities_written = 0

    for row in rows:
        chunk_id = row["chunk_id"]
        document_id = row["document_id"]
        text = row["text"] or ""
        timestamp_start = row["timestamp_start"] or None

        detected = detect_event(text)

        print(
            json.dumps(
                {
                    "chunk_id": chunk_id,
                    "event_detected": bool(detected),
                },
                ensure_ascii=False,
            )
        )

        if detected:
            if detected["event_type"] not in EVENT_TYPES:
                raise RuntimeError(f"Unsupported event_type: {detected['event_type']}")

            event_id = insert_event(
                document_id=document_id,
                chunk_id=chunk_id,
                event_type=detected["event_type"],
                event_time=timestamp_start,
                summary=detected["summary"],
                confidence=float(detected["confidence"]),
            )
            events_written += 1

            entity_ids = fetch_chunk_entity_ids(chunk_id)
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
