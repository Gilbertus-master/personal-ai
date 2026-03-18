from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_pg_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "gilbertus"),
        user=os.getenv("POSTGRES_USER", "gilbertus"),
        password=os.getenv("POSTGRES_PASSWORD", "gilbertus"),
    )