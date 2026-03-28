"""Omnius embedding + Qdrant vector search.

Generates embeddings for chunks via OpenAI and stores in Qdrant.
Used by /ask for semantic search alongside PostgreSQL FTS.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

QDRANT_URL = os.getenv("OMNIUS_QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("OMNIUS_QDRANT_COLLECTION", "omnius_ref")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("OMNIUS_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = 1536

_qdrant: QdrantClient | None = None


def get_qdrant() -> QdrantClient:
    """Get or create Qdrant client."""
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None, timeout=30)
        # Ensure collection exists
        collections = [c.name for c in _qdrant.get_collections().collections]
        if QDRANT_COLLECTION not in collections:
            _qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            log.info("qdrant_collection_created", collection=QDRANT_COLLECTION)
    return _qdrant


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings via OpenAI API."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY required for embeddings")

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": EMBEDDING_MODEL, "input": texts},
        )
    resp.raise_for_status()
    data = resp.json()
    return [item["embedding"] for item in data["data"]]


def embed_new_chunks(batch_size: int = 50, limit: int = 200) -> dict:
    """Embed chunks that don't have embedding_id yet."""
    stats = {"embedded": 0, "skipped": 0, "errors": 0}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.content, c.classification, d.owner_user_id, d.department
                FROM omnius_chunks c
                JOIN omnius_documents d ON d.id = c.document_id
                WHERE c.embedding_id IS NULL
                ORDER BY c.id
                LIMIT %s
            """, (limit,))
            chunks = cur.fetchall()

    if not chunks:
        return stats

    qdrant = get_qdrant()

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [row[1][:8000] for row in batch]  # Limit text length for embedding

        try:
            embeddings = embed_texts(texts)
        except Exception as e:
            log.error("embedding_failed", error=str(e), batch_start=i)
            stats["errors"] += len(batch)
            continue

        points = []
        embedding_updates = []

        for (chunk_id, content, classification, owner_id, department), vector in zip(batch, embeddings):
            point_id = str(uuid.uuid4())
            points.append(PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "chunk_id": chunk_id,
                    "classification": classification,
                    "owner_user_id": owner_id,
                    "department": department,
                    "text_preview": content[:200],
                },
            ))
            embedding_updates.append((point_id, chunk_id))

        # Store in Qdrant
        qdrant.upsert(collection_name=QDRANT_COLLECTION, points=points)

        # Update embedding_id in DB
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                for emb_id, chunk_id in embedding_updates:
                    cur.execute("UPDATE omnius_chunks SET embedding_id = %s WHERE id = %s",
                                (emb_id, chunk_id))
            conn.commit()

        stats["embedded"] += len(batch)

    log.info("embedding_complete", **stats)
    return stats


def search_vectors(query: str, classifications: list[str],
                   user_id: int | None = None, department: str | None = None,
                   limit: int = 15) -> list[dict[str, Any]]:
    """Semantic search in Qdrant with RBAC filtering."""
    try:
        query_embedding = embed_texts([query])[0]
    except Exception as e:
        log.error("query_embedding_failed", error=str(e))
        return []

    qdrant = get_qdrant()

    # Build Qdrant filter
    must_conditions = []

    # Classification filter
    if classifications:
        must_conditions.append({
            "key": "classification",
            "match": {"any": classifications},
        })

    # Department filter (for director/manager/specialist)
    if department:
        must_conditions.append({
            "should": [
                {"key": "department", "match": {"value": department}},
                {"is_null": {"key": "department"}},
            ]
        })

    query_filter = {"must": must_conditions} if must_conditions else None

    results = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_embedding,
        query_filter=query_filter,
        limit=limit,
    )

    # Fetch full chunk content from DB
    chunk_ids = [r.payload.get("chunk_id") for r in results if r.payload.get("chunk_id")]
    if not chunk_ids:
        return []

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.content, d.title, d.source_type, c.classification, d.owner_user_id
                FROM omnius_chunks c
                JOIN omnius_documents d ON d.id = c.document_id
                WHERE c.id = ANY(%s)
            """, (chunk_ids,))
            rows = {r[0]: r for r in cur.fetchall()}

    matches = []
    for result in results:
        chunk_id = result.payload.get("chunk_id")
        row = rows.get(chunk_id)
        if not row:
            continue

        # Filter personal docs — only owner can see
        if row[4] == "personal" and row[5] != user_id:
            continue

        matches.append({
            "chunk_id": row[0],
            "content": row[1],
            "title": row[2],
            "source_type": row[3],
            "classification": row[4],
            "score": result.score,
        })

    return matches
