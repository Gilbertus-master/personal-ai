import json
import subprocess


def _run_sql(sql: str, expect_rows: bool = True) -> str:
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "gilbertus-postgres",
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "gilbertus",
            "-d",
            "gilbertus",
            "-t",
            "-A",
        ],
        input=sql,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("SQL command failed.")
        print("STDOUT:")
        print(result.stdout)
        print("STDERR:")
        print(result.stderr)
        print("SQL:")
        print(sql)
        raise RuntimeError("Database command failed")

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    if not lines:
        if expect_rows:
            print("SQL command returned no rows.")
            print("STDOUT:")
            print(result.stdout)
            print("STDERR:")
            print(result.stderr)
            print("SQL:")
            print(sql)
            raise RuntimeError("Database command returned no rows")
        return ""

    return lines[0]


def _sql_escape(value: str) -> str:
    return value.replace("'", "''")


def get_connection():
    return None


def document_exists_by_raw_path(raw_path: str) -> bool:
    sql = f"""
    SELECT id
    FROM documents
    WHERE raw_path = '{_sql_escape(raw_path)}'
    LIMIT 1;
    """
    result = _run_sql(sql, expect_rows=False)
    return bool(result)


def insert_source(conn, source_type: str, source_name: str) -> int:
    sql = f"""
    INSERT INTO sources (source_type, source_name)
    VALUES ('{_sql_escape(source_type)}', '{_sql_escape(source_name)}')
    RETURNING id;
    """
    return int(_run_sql(sql))


def insert_document(
    conn,
    source_id: int,
    title: str,
    created_at,
    author: str | None,
    participants: list[str],
    raw_path: str,
) -> int:
    author_sql = "NULL" if author is None else f"'{_sql_escape(author)}'"
    created_at_sql = "NULL" if created_at is None else f"'{created_at.isoformat()}'"
    participants_json = json.dumps(participants, ensure_ascii=False)

    sql = f"""
    INSERT INTO documents (source_id, title, created_at, author, participants, raw_path)
    VALUES (
        {source_id},
        '{_sql_escape(title)}',
        {created_at_sql},
        {author_sql},
        '{_sql_escape(participants_json)}'::jsonb,
        '{_sql_escape(raw_path)}'
    )
    RETURNING id;
    """
    return int(_run_sql(sql))


def insert_chunk(
    conn,
    document_id: int,
    chunk_index: int,
    text: str,
    timestamp_start,
    timestamp_end,
    embedding_id: str | None = None,
) -> int:
    timestamp_start_sql = "NULL" if timestamp_start is None else f"'{timestamp_start.isoformat()}'"
    timestamp_end_sql = "NULL" if timestamp_end is None else f"'{timestamp_end.isoformat()}'"
    embedding_id_sql = "NULL" if embedding_id is None else f"'{_sql_escape(embedding_id)}'"

    sql = f"""
    INSERT INTO chunks (
        document_id,
        chunk_index,
        text,
        timestamp_start,
        timestamp_end,
        embedding_id
    )
    VALUES (
        {document_id},
        {chunk_index},
        '{_sql_escape(text)}',
        {timestamp_start_sql},
        {timestamp_end_sql},
        {embedding_id_sql}
    )
    RETURNING id;
    """
    return int(_run_sql(sql))