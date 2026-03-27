"""Omnius PostgreSQL connection pool — separate from Gilbertus DB."""
from __future__ import annotations

import os

import psycopg
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

_conninfo = psycopg.conninfo.make_conninfo(
    host=os.getenv("OMNIUS_POSTGRES_HOST", "127.0.0.1"),
    port=int(os.getenv("OMNIUS_POSTGRES_PORT", "5432")),
    dbname=os.getenv("OMNIUS_POSTGRES_DB", "omnius_ref"),
    user=os.getenv("OMNIUS_POSTGRES_USER", "omnius"),
    password=os.getenv("OMNIUS_POSTGRES_PASSWORD", "omnius"),
)

_pool = ConnectionPool(
    conninfo=_conninfo,
    min_size=3,
    max_size=30,
    timeout=30,
    open=True,
)


def get_pg_connection():
    """Return a connection from the Omnius pool. Use as context manager."""
    return _pool.connection()
