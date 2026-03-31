from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

_conninfo = psycopg.conninfo.make_conninfo(
    host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    dbname=os.getenv("POSTGRES_DB", "gilbertus"),
    user=os.getenv("POSTGRES_USER", "gilbertus"),
    password=os.getenv("POSTGRES_PASSWORD", "gilbertus"),
)

_pool = ConnectionPool(
    conninfo=_conninfo,
    min_size=int(os.getenv('PG_POOL_MIN_SIZE', '5')),
    max_size=10,
    open=True,
)


def get_pg_connection() -> Iterator[psycopg.Connection]:
    """Return a connection from the pool. Use as context manager:
        with get_pg_connection() as conn:
            ...
    Connection is returned to the pool on exit.
    """
    return _pool.connection()
