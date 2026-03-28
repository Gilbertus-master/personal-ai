from __future__ import annotations

import argparse
import os
import uuid
import tiktoken
from typing import Any
import httpx

import time
from openai import RateLimitError

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APITimeoutError
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import psycopg

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "gilbertus_chunks")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "gilbertus")
POSTGRES_USER = os.getenv("POSTGRES_USER", "gilbertus")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "gilbertus_local_password")

EMBEDDING_DIM = 3072  # text-embedding-3-large
MAX_EMBED_TOKENS = 8000
TOKENIZER = tiktoken.get_encoding("cl100k_base")

if not OPENAI_API_KEY:
    raise RuntimeError("Brak OPENAI_API_KEY w .env")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None)


def ensure_collection() -> None:
    collections = qdrant.get_collections().collections
    existing = {c.name for c in collections}
    if QDRANT_COLLECTION not in existing:
        qdrant.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


def get_pg_connection():
    from app.db.postgres import get_pg_connection as _pool_conn
    return _pool_conn()

def count_tokens(text: str) -> int:
    return len(TOKENIZER.encode(text or ""))

def fetch_unindexed_chunks(
    limit: int = 100,
    source_type: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.chunk_index,
            c.text,
            c.timestamp_start,
            c.timestamp_end,
            d.title,
            d.created_at,
            d.author,
            d.participants,
            d.raw_path,
            s.source_type,
            s.source_name
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE c.embedding_id IS NULL
          AND COALESCE(c.embedding_status, 'pending') = 'pending'
    """
    params: list[Any] = []

    if source_type:
        query += " AND s.source_type = %s"
        params.append(source_type)

    query += """
        ORDER BY c.id
        LIMIT %s
    """
    params.append(limit)

    with get_pg_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(query, tuple(params))
            return cur.fetchall()


def embed_texts(texts: list[str], max_retries: int = 10) -> list[list[float]]:
    attempt = 0

    while True:
        try:
            resp = openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
            )
            from app.db.cost_tracker import log_openai_cost
            if hasattr(resp, "usage") and hasattr(resp.usage, "total_tokens"):
                log_openai_cost(EMBEDDING_MODEL, "retrieval.embeddings", resp.usage.total_tokens)
            return [item.embedding for item in resp.data]

        except RateLimitError:
            attempt += 1
            if attempt > max_retries:
                print(f"Rate limit retry limit exceeded after {max_retries} attempts.")
                raise

            sleep_seconds = min(2 ** attempt, 30)
            print(
                f"Rate limit hit while embedding batch of {len(texts)} texts. "
                f"Retry {attempt}/{max_retries} in {sleep_seconds}s..."
            )
            time.sleep(sleep_seconds)

        except (APIConnectionError, APITimeoutError, httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            attempt += 1
            if attempt > max_retries:
                print(f"Connection retry limit exceeded after {max_retries} attempts.")
                raise

            sleep_seconds = min(2 ** attempt, 30)
            print(
                f"Connection error while embedding batch of {len(texts)} texts: {type(e).__name__}. "
                f"Retry {attempt}/{max_retries} in {sleep_seconds}s..."
            )
            time.sleep(sleep_seconds)


def update_chunk_mapping(mappings: list[tuple[str, str]]) -> None:
    query = """
        UPDATE chunks
        SET embedding_id = %s,
            embedding_status = 'done',
            embedding_error = NULL
        WHERE id = %s
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, mappings)
        conn.commit()

def mark_chunks_skipped(skipped_rows: list[tuple[str, int, str]]) -> None:
    query = """
        UPDATE chunks
        SET embedding_status = 'skipped',
            embedding_error = %s
        WHERE id = %s
    """
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                query,
                [(f"too_many_tokens:{token_count}", chunk_id) for chunk_id, token_count, _ in skipped_rows]
            )
        conn.commit()

def build_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": row["chunk_id"],
        "document_id": row["document_id"],
        "chunk_index": row["chunk_index"],
        "source_type": row["source_type"],
        "source_name": row["source_name"],
        "title": row["title"],
        "author": row["author"],
        "participants": row["participants"],
        "created_at": str(row["created_at"]) if row["created_at"] else None,
        "timestamp_start": str(row["timestamp_start"]) if row["timestamp_start"] else None,
        "timestamp_end": str(row["timestamp_end"]) if row["timestamp_end"] else None,
        "raw_path": row["raw_path"],
        "text": row["text"],
    }


def index_batch(
    limit: int = 100,
    source_type: str | None = None,
) -> int:
    rows = fetch_unindexed_chunks(limit=limit, source_type=source_type)
    if not rows:
        print("Brak nowych chunków do zaindeksowania.")
        return 0

    safe_rows = []
    skipped_rows = []

    for row in rows:
        token_count = count_tokens(row["text"])
        if token_count > MAX_EMBED_TOKENS:
            skipped_rows.append((row["chunk_id"], token_count, row["title"]))
        else:
            safe_rows.append(row)

    for chunk_id, token_count, title in skipped_rows:
        print(f"Pominięto za długi chunk: chunk_id={chunk_id}, tokens={token_count}, title={title}")
    if skipped_rows:
        mark_chunks_skipped(skipped_rows)

    if not safe_rows:
        print("W tej paczce wszystkie chunki były za długie.")
        return 0

    texts = [row["text"] for row in safe_rows]
    embeddings = embed_texts(texts)

    points: list[PointStruct] = []
    mappings: list[tuple[str, str]] = []

    for row, vector in zip(safe_rows, embeddings):
        point_id = str(uuid.uuid4())
        payload = build_payload(row)
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))
        mappings.append((point_id, row["chunk_id"]))

    qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)
    update_chunk_mapping(mappings)

    if source_type:
        print(f"Zaindeksowano {len(points)} chunków dla source_type={source_type}.")
    else:
        print(f"Zaindeksowano {len(points)} chunków.")

    return len(points)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-type", dest="source_type", default=None)
    parser.add_argument("--limit", dest="limit", type=int, default=None)
    parser.add_argument("--batch-size", dest="batch_size", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    ensure_collection()
    total = 0

    remaining_limit = args.limit

    while True:
        batch_limit = args.batch_size
        if remaining_limit is not None:
            if remaining_limit <= 0:
                break
            batch_limit = min(batch_limit, remaining_limit)

        inserted = index_batch(
            limit=batch_limit,
            source_type=args.source_type,
        )

        total += inserted

        if remaining_limit is not None:
            remaining_limit -= inserted

        if inserted == 0:
            break

    if args.source_type:
        print(f"Gotowe. Łącznie zaindeksowano: {total} chunków dla source_type={args.source_type}")
    else:
        print(f"Gotowe. Łącznie zaindeksowano: {total}")


if __name__ == "__main__":
    main()
