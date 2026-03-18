from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

from app.db.postgres import get_pg_connection

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "gilbertus_chunks")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

client = OpenAI(api_key=OPENAI_API_KEY)
qdrant = QdrantClient(url=QDRANT_URL)


def embed_query(text: str) -> list[float]:
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return resp.data[0].embedding


def fetch_document_metadata(document_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not document_ids:
        return {}

    query = """
    SELECT
        d.id AS document_id,
        d.title,
        d.created_at,
        d.raw_path,
        s.source_type,
        s.source_name
    FROM documents d
    JOIN sources s ON d.source_id = s.id
    WHERE d.id = ANY(%s)
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (document_ids,))
            rows = cur.fetchall()

    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        document_id, title, created_at, raw_path, source_type, source_name = row
        result[document_id] = {
            "document_id": document_id,
            "title": title,
            "created_at": created_at.isoformat() if created_at else None,
            "raw_path": raw_path,
            "source_type": source_type,
            "source_name": source_name,
        }
    return result


def _date_in_range(created_at: str | None, date_from: str | None, date_to: str | None) -> bool:
    if not created_at:
        return True

    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return True

    if date_from:
        dt_from = datetime.fromisoformat(f"{date_from}T00:00:00")
        if created.replace(tzinfo=None) < dt_from:
            return False

    if date_to:
        dt_to = datetime.fromisoformat(f"{date_to}T23:59:59")
        if created.replace(tzinfo=None) > dt_to:
            return False

    return True


def filter_matches(
    matches: list[dict[str, Any]],
    *,
    question_type: str = "retrieval",
) -> list[dict[str, Any]]:
    score_threshold_map = {
        "retrieval": 0.43,
        "summary": 0.42,
        "analysis": 0.40,
        "chronology": 0.48,
    }

    max_per_document_map = {
        "retrieval": 2,
        "summary": 3,
        "analysis": 4,
        "chronology": 2,
    }

    score_threshold = score_threshold_map.get(question_type, 0.42)
    max_per_document = max_per_document_map.get(question_type, 3)

    filtered_by_score = [
        m for m in matches
        if float(m.get("score", 0.0)) >= score_threshold
    ]

    deduped: list[dict[str, Any]] = []
    seen_keys: set[tuple[Any, str]] = set()

    for m in filtered_by_score:
        text = (m.get("text") or "").strip()
        normalized_prefix = " ".join(text[:220].split()).lower()
        dedupe_key = (m.get("document_id"), normalized_prefix)

        if dedupe_key in seen_keys:
            continue

        seen_keys.add(dedupe_key)
        deduped.append(m)

    result: list[dict[str, Any]] = []
    per_document_counter: dict[Any, int] = {}

    for m in deduped:
        document_id = m.get("document_id")
        current_count = per_document_counter.get(document_id, 0)

        if current_count >= max_per_document:
            continue

        per_document_counter[document_id] = current_count + 1
        result.append(m)

    return result


def search_chunks(
    query: str,
    top_k: int = 8,
    source_types: list[str] | None = None,
    source_names: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    prefetch_k: int | None = None,
    question_type: str = "retrieval",
) -> list[dict[str, Any]]:
    limit = prefetch_k or max(top_k * 3, 20)

    hits = qdrant.query_points(
        collection_name=QDRANT_COLLECTION,
        query=embed_query(query),
        limit=limit,
        with_payload=True,
    ).points

    raw_matches: list[dict[str, Any]] = []
    document_ids: list[int] = []

    for hit in hits:
        payload = hit.payload or {}
        document_id = payload.get("document_id")

        if document_id is not None:
            document_ids.append(document_id)

        raw_matches.append(
            {
                "chunk_id": payload.get("chunk_id"),
                "document_id": document_id,
                "score": float(hit.score),
                "title": payload.get("title"),
                "source_name": payload.get("source_name"),
                "text": payload.get("text") or "",
            }
        )

    metadata_map = fetch_document_metadata(sorted(set(document_ids)))

    enriched: list[dict[str, Any]] = []
    for match in raw_matches:
        document_id = match.get("document_id")
        meta = metadata_map.get(document_id, {})

        enriched_match = {
            **match,
            "title": meta.get("title") or match.get("title"),
            "source_type": meta.get("source_type"),
            "source_name": meta.get("source_name") or match.get("source_name"),
            "created_at": meta.get("created_at"),
        }

        if source_types and enriched_match.get("source_type") not in source_types:
            continue

        if source_names and enriched_match.get("source_name") not in source_names:
            continue

        if not _date_in_range(enriched_match.get("created_at"), date_from, date_to):
            continue

        enriched.append(enriched_match)

    cleaned = filter_matches(enriched, question_type=question_type)

    return cleaned[:top_k]
