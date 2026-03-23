import json
from typing import Any

from app.db.postgres import get_pg_connection


def get_connection():
    """Legacy no-op. Connection management is handled internally by each function."""
    return None


def document_exists_by_raw_path(raw_path: str) -> bool:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM documents WHERE raw_path = %s LIMIT 1",
                (raw_path,),
            )
            row = cur.fetchone()
            return row is not None and row[0] > 0


def insert_source(conn, source_type: str, source_name: str) -> int:
    with get_pg_connection() as pg:
        with pg.cursor() as cur:
            cur.execute(
                "INSERT INTO sources (source_type, source_name) VALUES (%s, %s) RETURNING id",
                (source_type, source_name),
            )
            row = cur.fetchone()
        pg.commit()
    return row[0]


def insert_document(
    conn,
    source_id: int,
    title: str,
    created_at,
    author: str | None,
    participants: list[str],
    raw_path: str,
) -> int:
    participants_json = json.dumps(participants, ensure_ascii=False)
    created_at_val = created_at.isoformat() if created_at else None

    with get_pg_connection() as pg:
        with pg.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (source_id, title, created_at, author, participants, raw_path)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                RETURNING id
                """,
                (source_id, title, created_at_val, author, participants_json, raw_path),
            )
            row = cur.fetchone()
        pg.commit()
    return row[0]


def insert_chunk(
    conn,
    document_id: int,
    chunk_index: int,
    text: str,
    timestamp_start,
    timestamp_end,
    embedding_id: str | None = None,
) -> int:
    ts_start = timestamp_start.isoformat() if timestamp_start else None
    ts_end = timestamp_end.isoformat() if timestamp_end else None

    with get_pg_connection() as pg:
        with pg.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chunks (document_id, chunk_index, text, timestamp_start, timestamp_end, embedding_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (document_id, chunk_index, text, ts_start, ts_end, embedding_id),
            )
            row = cur.fetchone()
        pg.commit()
    return row[0]


def get_document_row(document_id: int) -> dict[str, str] | None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_id, COALESCE(title, ''), COALESCE(author, ''),
                       COALESCE(raw_path, ''), COALESCE(created_at::text, '')
                FROM documents
                WHERE id = %s
                LIMIT 1
                """,
                (document_id,),
            )
            rows = cur.fetchall()

    if not rows:
        return None
    row = rows[0]

    return {
        "id": str(row[0]),
        "source_id": str(row[1]),
        "title": row[2],
        "author": row[3],
        "raw_path": row[4],
        "created_at": row[5],
    }


def delete_chunks_for_document(document_id: int) -> None:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
        conn.commit()


def update_document_metadata(
    document_id: int,
    title: str,
    created_at,
    author: str | None,
    participants: list[str],
) -> None:
    created_at_val = created_at.isoformat() if created_at else None
    participants_json = json.dumps(participants, ensure_ascii=False)

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE documents
                SET title = %s, created_at = %s, author = %s, participants = %s::jsonb
                WHERE id = %s
                """,
                (title, created_at_val, author, participants_json, document_id),
            )
        conn.commit()


def get_chunk_stats_for_document(document_id: int) -> dict[str, int]:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(length(text)), 0)
                FROM chunks
                WHERE document_id = %s
                """,
                (document_id,),
            )
            rows = cur.fetchall()

    if not rows:
        return {"chunk_count": 0, "total_chars": 0}

    return {
        "chunk_count": int(rows[0][0]),
        "total_chars": int(rows[0][1]),
    }


def run_query(sql: str, params: tuple = (), expect_rows: bool = True) -> list[tuple]:
    """Generic parameterized query runner. Returns list of tuples."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description is None:
                conn.commit()
                return []
            rows = cur.fetchall()
    if not rows and expect_rows:
        raise RuntimeError(f"Query returned no rows: {sql[:200]}")
    return rows


def run_query_single(sql: str, params: tuple = (), expect_row: bool = True) -> str:
    """Run parameterized query returning first column of first row as string."""
    rows = run_query(sql, params, expect_rows=expect_row)
    if not rows:
        return ""
    return str(rows[0][0])


def run_query_column(sql: str, params: tuple = ()) -> list[str]:
    """Run parameterized query returning first column of all rows as strings."""
    rows = run_query(sql, params, expect_rows=False)
    return [str(row[0]) for row in rows]


# ─── Legacy wrappers (psycopg-backed, no more docker exec) ───
# These accept raw SQL strings for callers not yet migrated to parameterized queries.
# They execute via psycopg directly — no subprocess, no docker exec.

def _run_sql(sql: str, expect_rows: bool = True) -> str:
    """Legacy wrapper: executes raw SQL via psycopg, returns first value as string."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                conn.commit()
                return ""
            row = cur.fetchone()
        conn.commit()

    if row is None:
        if expect_rows:
            raise RuntimeError(f"Query returned no rows: {sql[:200]}")
        return ""

    return str(row[0])


def _run_sql_all_lines(sql: str) -> list[str]:
    """Legacy wrapper: executes raw SQL via psycopg, returns all rows as pipe-delimited strings."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                conn.commit()
                return []
            rows = cur.fetchall()

    lines = []
    for row in rows:
        line = "|".join(str(col) if col is not None else "" for col in row)
        lines.append(line)
    return lines
