import json
import sys
from datetime import datetime
from typing import Any

import structlog

from app.db.postgres import get_pg_connection

log = structlog.get_logger()

DEFAULT_LIMIT = 20


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
            if i + 1 >= len(sys.argv):
                raise ValueError(f"{arg} requires a value")
            args["event_type"] = sys.argv[i + 1]
            i += 2
        elif arg == "--date-from":
            if i + 1 >= len(sys.argv):
                raise ValueError(f"{arg} requires a value")
            args["date_from"] = sys.argv[i + 1]
            i += 2
        elif arg == "--date-to":
            if i + 1 >= len(sys.argv):
                raise ValueError(f"{arg} requires a value")
            args["date_to"] = sys.argv[i + 1]
            i += 2
        elif arg == "--limit":
            if i + 1 >= len(sys.argv):
                raise ValueError(f"{arg} requires a value")
            limit = int(sys.argv[i + 1])
            if limit <= 0 or limit > 500:
                raise ValueError(f"--limit must be between 1 and 500, got {limit}")
            args["limit"] = limit
            i += 2
        else:
            raise ValueError(f"Unknown argument: {arg}")

    return args


def _validate_date(date_str: str, field_name: str) -> None:
    """Validate that a date string is in ISO format.

    Args:
        date_str: The date string to validate.
        field_name: The field name (for error messages).

    Raises:
        ValueError: If the date string is not in valid ISO format.
    """
    try:
        datetime.fromisoformat(date_str)
    except ValueError as e:
        raise ValueError(
            f"Invalid {field_name} format. Expected ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS): {date_str}"
        ) from e


def build_query(
    event_type: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
) -> tuple[str, list[Any]]:
    where_clauses: list[str] = []
    params: list[Any] = []

    if event_type:
        where_clauses.append("e.event_type = %s")
        params.append(event_type)

    if date_from:
        _validate_date(date_from, "date_from")
        where_clauses.append("e.event_time >= %s::timestamptz")
        params.append(date_from)

    if date_to:
        _validate_date(date_to, "date_to")
        where_clauses.append("e.event_time <= %s::timestamptz")
        params.append(date_to)

    where_sql = "WHERE 1=1"
    if where_clauses:
        where_sql += " AND " + " AND ".join(where_clauses)

    sql = """
    SELECT
        e.id,
        COALESCE(e.event_time::text, ''),
        e.event_type,
        e.document_id,
        e.chunk_id,
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
    """ + where_sql + """
    GROUP BY e.id, e.event_time, e.event_type, e.document_id, e.chunk_id, e.summary
    ORDER BY e.event_time NULLS LAST, e.id
    LIMIT %s
    """
    params.append(limit)

    return sql, params


def query_timeline(
    event_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    sql, params = build_query(event_type, date_from, date_to, limit)

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
    except Exception as e:
        log.error(
            "timeline_query_failed",
            error=str(e),
            event_type=event_type,
            date_from=date_from,
            date_to=date_to,
        )
        raise

    result = []
    for row in rows:
        raw_entities = row[6].strip() if row[6] else ""
        entities = [item.strip() for item in raw_entities.split(" || ") if item.strip()] if raw_entities else []

        result.append(
            {
                "event_id": row[0],
                "event_time": row[1] or None,
                "event_type": row[2],
                "document_id": row[3],
                "chunk_id": row[4],
                "summary": row[5],
                "entities": entities,
            }
        )
    return result


def main() -> None:
    args = parse_args()
    rows = query_timeline(
        event_type=args["event_type"],
        date_from=args["date_from"],
        date_to=args["date_to"],
        limit=args["limit"],
    )

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
