import json
import sys
from typing import Any

from app.ingestion.common.db import _run_sql_all_lines


DEFAULT_LIMIT = 20


def sql_escape(value: str) -> str:
    return value.replace("'", "''")


def parse_args() -> dict[str, Any]:
    args = {
        "event_type": None,
        "date_from": None,
        "date_to": None,
        "limit": DEFAULT_LIMIT,
    }

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]

        if arg == "--event-type":
            args["event_type"] = sys.argv[i + 1]
            i += 2
        elif arg == "--date-from":
            args["date_from"] = sys.argv[i + 1]
            i += 2
        elif arg == "--date-to":
            args["date_to"] = sys.argv[i + 1]
            i += 2
        elif arg == "--limit":
            args["limit"] = int(sys.argv[i + 1])
            i += 2
        else:
            raise ValueError(f"Unknown argument: {arg}")

    return args


def build_query(event_type: str | None, date_from: str | None, date_to: str | None, limit: int) -> str:
    where_clauses = []

    if event_type:
        where_clauses.append(f"e.event_type = '{sql_escape(event_type)}'")

    if date_from:
        where_clauses.append(f"e.event_time >= '{sql_escape(date_from)}'::timestamptz")

    if date_to:
        where_clauses.append(f"e.event_time <= '{sql_escape(date_to)}'::timestamptz")

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    sql = f"""
    SELECT
        e.id::text,
        COALESCE(e.event_time::text, ''),
        e.event_type,
        e.document_id::text,
        e.chunk_id::text,
        replace(replace(e.summary, E'\t', ' '), E'\n', ' ') AS summary,
        COALESCE(
            string_agg(
                DISTINCT replace(replace(en.canonical_name, E'\t', ' '), E'\n', ' '),
                ' || '
                ORDER BY replace(replace(en.canonical_name, E'\t', ' '), E'\n', ' ')
            ),
            ''
        ) AS entities
    FROM events e
    LEFT JOIN event_entities ee ON ee.event_id = e.id
    LEFT JOIN entities en ON en.id = ee.entity_id
    {where_sql}
    GROUP BY e.id, e.event_time, e.event_type, e.document_id, e.chunk_id, e.summary
    ORDER BY e.event_time NULLS LAST, e.id
    LIMIT {limit};
    """
    return sql


def parse_rows(lines: list[str]) -> list[dict[str, Any]]:
    rows = []
    for line in lines:
        parts = line.split("|", 6)
        if len(parts) != 7:
            continue

        raw_entities = parts[6].strip()
        entities = [item.strip() for item in raw_entities.split("||") if item.strip()] if raw_entities else []

        rows.append(
            {
                "event_id": int(parts[0]),
                "event_time": parts[1] or None,
                "event_type": parts[2],
                "document_id": int(parts[3]),
                "chunk_id": int(parts[4]),
                "summary": parts[5],
                "entities": entities,
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    sql = build_query(
        event_type=args["event_type"],
        date_from=args["date_from"],
        date_to=args["date_to"],
        limit=args["limit"],
    )
    rows = parse_rows(_run_sql_all_lines(sql))

    print(
        json.dumps(
            {
                "filters": args,
                "count": len(rows),
                "events": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
