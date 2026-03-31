from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError
from app.utils.dns_patch import apply_dns_patch
apply_dns_patch(["api.openai.com"])
from qdrant_client import QdrantClient

from app.db.postgres import get_pg_connection

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "gilbertus_chunks")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

client = OpenAI(api_key=OPENAI_API_KEY, timeout=30.0)
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY if QDRANT_API_KEY else None, timeout=15.0)


def resolve_person_aliases(query: str) -> str:
    """If query mentions a known person, expand with their aliases and canonical name.
    This improves semantic search by matching multiple name forms.
    """
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Find people mentioned in query (fuzzy match against known names)
                cur.execute("""
                    SELECT p.first_name, p.last_name, p.aliases,
                           e.canonical_name, r.person_role, r.organization
                    FROM people p
                    LEFT JOIN entities e ON e.id = p.entity_id
                    LEFT JOIN relationships r ON r.person_id = p.id
                    WHERE p.first_name IS NOT NULL
                """)
                people = cur.fetchall()

        expansions = []
        expansions_list = []
        query_lower = query.lower()

        # Organization-level aliases
        ORG_ALIASES = {
            "reh": ["Respect Energy Holding", "Respect Energy S.A.", "REH"],
            "ref": ["Respect Energy Fuels", "Gaselle", "RE-Fuels", "REF"],
            "re": ["Respect Energy", "RE"],
        }
        query_words = query_lower.split()
        for short, org_expansions in ORG_ALIASES.items():
            if short in query_words or any(e.lower() in query_lower for e in org_expansions):
                for exp in org_expansions:
                    if exp.lower() not in query_lower:
                        expansions_list.append(exp)

        for first, last, aliases, canonical, role, org in people:
            # Check if person is mentioned in query (last name, first name, or full name)
            full_name = f"{first} {last}".lower()
            first_lower = first.lower() if first else ""
            last_lower = last.lower() if last else ""
            if last_lower in query_lower or full_name in query_lower or (len(first_lower) > 3 and first_lower in query_lower):
                # Add canonical name and role context
                parts = [canonical] if canonical else [f"{first} {last}"]
                if role:
                    parts.append(role)
                if org:
                    parts.append(org)
                if aliases:
                    for alias in aliases[:3]:
                        if alias.lower() not in query_lower:
                            parts.append(alias)
                expansions.append(" ".join(parts))

        if expansions_list:
            expansions.append(" ".join(expansions_list))

        if expansions:
            return f"{query} ({'; '.join(expansions)})"
    except Exception:
        pass

    return query


def embed_query(text: str) -> list[float]:
    try:
        resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text, timeout=10.0)
        from app.db.cost_tracker import log_openai_cost
        if hasattr(resp, "usage") and hasattr(resp.usage, "total_tokens"):
            log_openai_cost(EMBEDDING_MODEL, "retrieval.query_embed", resp.usage.total_tokens)
        return resp.data[0].embedding
    except (APIConnectionError, APITimeoutError) as e:
        import structlog as _sl
        _sl.get_logger().warning("embed_query.openai_unavailable", error=str(e))
        return []  # Empty vector — fallback to keyword search
    except RateLimitError as e:
        raise RuntimeError(f"OpenAI embedding rate limit hit: {e}") from e
    except Exception as e:
        import structlog as _sl
        _sl.get_logger().warning("embed_query.failed", error=str(e))
        return []  # Fallback to keyword search


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

def fetch_existing_chunk_ids(chunk_ids: list[int]) -> set[int]:
    if not chunk_ids:
        return set()

    query = """
    SELECT id
    FROM chunks
    WHERE id = ANY(%s)
    """

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (chunk_ids,))
            rows = cur.fetchall()

    return {row[0] for row in rows}

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
        if m.get("search_type") == "hybrid_rrf"
        or float(m.get("score", 0.0)) >= score_threshold
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



def _keyword_search_fallback(
    query: str,
    top_k: int = 8,
    source_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Full-text keyword fallback when vector embeddings are unavailable."""
    from app.db.postgres import get_pg_connection
    terms = [t.strip() for t in query.split() if len(t.strip()) > 2][:6]
    if not terms:
        return []
    like_clauses = " AND ".join("c.text ILIKE %s" for _ in terms)
    params: list = [f"%{t}%" for t in terms]

    type_filter = ""
    if source_types:
        placeholders = ",".join(["%s"] * len(source_types))
        type_filter = f" AND d.source_type IN ({placeholders})"
        params += source_types

    params.append(top_k)

    sql = f"""
        SELECT c.id, c.document_id, c.text, s.source_type, s.source_name,
               d.title, d.created_at, 0.5 as score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE {like_clauses}{type_filter}
        ORDER BY d.created_at DESC
        LIMIT %s
    """
    results = []
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                for row in cur.fetchall():
                    results.append({
                        "chunk_id": row[0],
                        "document_id": row[1],
                        "text": row[2] or "",
                        "source_type": row[3],
                        "source_name": row[4],
                        "title": row[5],
                        "date": str(row[6]) if row[6] else None,
                        "score": row[7],
                    })
    except Exception as e:
        import structlog as _sl
        _sl.get_logger().warning("keyword_fallback.failed", error=str(e))
    return results


def _bm25_search(
    query: str,
    top_k: int = 50,
    source_types: list[str] | None = None,
    source_names: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Full-text search using PostgreSQL tsvector + ts_rank (BM25-like).
    Returns results sorted by relevance with rank scores."""
    where_clauses = ["c.text_tsv @@ plainto_tsquery('simple', %s)", "c.text IS NOT NULL"]
    params: list = [query]

    if source_types:
        placeholders = ",".join(["%s"] * len(source_types))
        where_clauses.append(f"s.source_type IN ({placeholders})")
        params.extend(source_types)

    if source_names:
        placeholders = ",".join(["%s"] * len(source_names))
        where_clauses.append(f"s.source_name IN ({placeholders})")
        params.extend(source_names)

    if date_from:
        where_clauses.append("d.created_at >= %s")
        params.append(date_from)

    if date_to:
        where_clauses.append("d.created_at <= %s")
        params.append(date_to)

    params.append(top_k)

    sql = f"""
        SELECT
            c.id as chunk_id,
            c.document_id,
            c.text,
            s.source_type,
            s.source_name,
            d.title,
            d.created_at,
            ts_rank(c.text_tsv, plainto_tsquery('simple', %s)) as bm25_score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY bm25_score DESC
        LIMIT %s
    """
    all_params = [query] + params

    results = []
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, all_params)
                for row in cur.fetchall():
                    results.append({
                        "chunk_id": row[0],
                        "document_id": row[1],
                        "text": row[2] or "",
                        "source_type": row[3],
                        "source_name": row[4],
                        "title": row[5],
                        "date": str(row[6]) if row[6] else None,
                        "score": float(row[7]),
                        "search_type": "bm25",
                    })
    except Exception as e:
        import structlog as _sl
        _sl.get_logger().warning("bm25_search.failed", error=str(e))
    return results


def _rrf_merge(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion: combine vector and BM25 results.
    RRF score = 1/(k + rank_vector) + 1/(k + rank_bm25)
    """
    rrf_scores: dict[int, float] = {}
    result_map: dict[int, dict] = {}

    for rank, item in enumerate(vector_results, 1):
        cid = item.get("chunk_id")
        if cid is None:
            continue
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)
        result_map[cid] = item

    for rank, item in enumerate(bm25_results, 1):
        cid = item.get("chunk_id")
        if cid is None:
            continue
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in result_map:
            result_map[cid] = item

    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    merged = []
    for cid in sorted_ids:
        item = result_map[cid].copy()
        item["score"] = rrf_scores[cid]
        item["search_type"] = "hybrid_rrf"
        merged.append(item)

    return merged


def _date_filtered_search(
    query: str,
    top_k: int,
    date_from: str | None,
    date_to: str | None,
    source_types: list[str] | None,
    source_names: list[str] | None,
    query_vector: list[float] | None,
) -> list[dict[str, Any]]:
    """When date range is specified: fetch from SQL, rerank by vector similarity."""
    import structlog as _sl
    _sl.get_logger().info("date_filtered_search", date_from=date_from, date_to=date_to)

    where_clauses = ["1=1"]
    params: list = []

    if date_from:
        where_clauses.append("d.created_at >= %s::timestamptz")
        params.append(f"{date_from}T00:00:00+00:00")
    if date_to:
        where_clauses.append("d.created_at <= %s::timestamptz")
        params.append(f"{date_to}T23:59:59+00:00")
    if source_types:
        ph = ",".join(["%s"] * len(source_types))
        where_clauses.append(f"s.source_type IN ({ph})")
        params += source_types
    if source_names:
        ph = ",".join(["%s"] * len(source_names))
        where_clauses.append(f"s.source_name IN ({ph})")
        params += source_names

    where_sql = " AND ".join(where_clauses)
    params.append(max(top_k * 5, 50))

    sql = f"""
        SELECT c.id, c.document_id, c.text, s.source_type, s.source_name,
               d.title, d.created_at, d.author, d.participants
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE {where_sql}
        ORDER BY d.created_at DESC
        LIMIT %s
    """

    rows = []
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    if not rows:
        return []

    results = []
    for row in rows:
        results.append({
            "chunk_id": row[0],
            "document_id": row[1],
            "text": row[2] or "",
            "source_type": row[3],
            "source_name": row[4],
            "title": row[5],
            "created_at": row[6].isoformat() if row[6] else None,
            "author": row[7],
            "participants": row[8],
            "score": 0.5,  # default score, override below if vector available
        })

    # Rerank by vector similarity if query_vector available
    if query_vector and results:
        from qdrant_client import models as qmodels
        chunk_ids = [r["chunk_id"] for r in results if r["chunk_id"]]
        if chunk_ids:
            try:
                hits = qdrant.query_points(
                    collection_name=QDRANT_COLLECTION,
                    query=query_vector,
                    query_filter=qmodels.Filter(
                        must=[qmodels.HasIdCondition(has_id=chunk_ids)]
                    ),
                    limit=len(chunk_ids),
                    with_payload=False,
                ).points
                score_map = {h.id: h.score for h in hits}
                for r in results:
                    r["score"] = score_map.get(r["chunk_id"], 0.3)
                results.sort(key=lambda x: x["score"], reverse=True)
            except Exception:
                pass  # Keep default ordering if Qdrant filter fails

    return results[:top_k]

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

    # Expand query with person aliases for better recall
    expanded_query = resolve_person_aliases(query)

    query_vector = embed_query(expanded_query)

    if not query_vector:
        # OpenAI unavailable — fallback to keyword search via PostgreSQL
        import structlog as _sl
        _sl.get_logger().info("search_chunks.keyword_fallback", query=query[:80])
        return _keyword_search_fallback(query, top_k, source_types)

    # When date range explicitly specified — use SQL pre-filter + vector reranking
    if date_from or date_to:
        return _date_filtered_search(
            query=query, top_k=top_k,
            date_from=date_from, date_to=date_to,
            source_types=source_types, source_names=source_names,
            query_vector=query_vector,
        )

    try:
        hits = qdrant.query_points(
            collection_name=QDRANT_COLLECTION,
            query=query_vector,
            limit=limit,
            with_payload=True,
        ).points
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Qdrant search failed: {e}") from e

    raw_matches: list[dict[str, Any]] = []
    document_ids: list[int] = []
    chunk_ids: list[int] = []

    for hit in hits:
        payload = hit.payload or {}
        document_id = payload.get("document_id")

        if document_id is not None:
            document_ids.append(document_id)

        chunk_id = payload.get("chunk_id")
        if chunk_id is not None:
            chunk_ids.append(chunk_id)

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
    existing_chunk_ids = fetch_existing_chunk_ids(sorted(set(chunk_ids)))

    enriched: list[dict[str, Any]] = []
    for match in raw_matches:
        document_id = match.get("document_id")
        meta = metadata_map.get(document_id, {})

        chunk_id = match.get("chunk_id")
        if chunk_id is None or chunk_id not in existing_chunk_ids:
            continue

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

    # Hybrid: also run BM25 search and merge via RRF
    try:
        bm25_hits = _bm25_search(
            query=query,
            top_k=limit,
            source_types=source_types,
            source_names=source_names,
            date_from=date_from,
            date_to=date_to,
        )
        if bm25_hits:
            enriched = _rrf_merge(enriched, bm25_hits)
    except Exception as _e:
        import structlog as _sl
        _sl.get_logger().warning("hybrid_search.bm25_failed", error=str(_e))

    cleaned = filter_matches(enriched, question_type=question_type)

    return cleaned[:top_k]
