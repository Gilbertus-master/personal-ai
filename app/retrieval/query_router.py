"""
Deep Routing: specialized retrieval strategies per question_type.

Routes:
  - retrieval:  standard vector search (unchanged)
  - chronology: vector search + timeline events (SQL), merged by date
  - summary:    vector search (standard path)
  - analysis:   parallel retrieval with alternate queries

Implements Anthropic "Routing" pattern — distinct categories get
fundamentally different processing, not just parameter tweaks.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import structlog

from app.models.query import InterpretedQuery
from app.retrieval.retriever import search_chunks

log = structlog.get_logger("query_router")


def route_retrieval(
    interpreted: InterpretedQuery,
    *,
    top_k: int,
    prefetch_k: int,
    enable_parallel: bool = False,
) -> list[dict]:
    """
    Route retrieval based on question_type.
    Returns list of match dicts (same format as search_chunks).
    """
    qt = interpreted.question_type

    if qt == "chronology":
        return _route_chronology(interpreted, top_k=top_k, prefetch_k=prefetch_k)
    elif qt == "analysis" and enable_parallel and interpreted.alternate_queries:
        return _route_analysis_parallel(interpreted, top_k=top_k, prefetch_k=prefetch_k)
    else:
        # Default: standard vector search (retrieval, summary, or analysis without alternates)
        return search_chunks(
            query=interpreted.normalized_query,
            top_k=top_k,
            source_types=interpreted.source_types,
            source_names=interpreted.source_names,
            date_from=interpreted.date_from,
            date_to=interpreted.date_to,
            prefetch_k=prefetch_k,
            question_type=interpreted.question_type,
        )


def _route_chronology(
    interpreted: InterpretedQuery,
    *,
    top_k: int,
    prefetch_k: int,
) -> list[dict]:
    """Chronology: vector search + timeline events from DB, merged."""
    # Vector search (standard)
    vector_matches = search_chunks(
        query=interpreted.normalized_query,
        top_k=top_k,
        source_types=interpreted.source_types,
        source_names=interpreted.source_names,
        date_from=interpreted.date_from,
        date_to=interpreted.date_to,
        prefetch_k=prefetch_k,
        question_type="chronology",
    )

    # Timeline events from PostgreSQL
    try:
        from app.retrieval.timeline import query_timeline
        timeline_events = query_timeline(
            event_type=None,
            date_from=interpreted.date_from,
            date_to=interpreted.date_to,
            limit=top_k,
        )

        # Convert timeline events to match-like dicts for compatibility
        for evt in timeline_events:
            # Check if this event's chunk is already in vector_matches
            existing_chunk_ids = {m.get("chunk_id") for m in vector_matches if m.get("chunk_id")}
            if evt.get("chunk_id") and evt["chunk_id"] not in existing_chunk_ids:
                vector_matches.append({
                    "chunk_id": evt["chunk_id"],
                    "document_id": evt["document_id"],
                    "score": 0.5,  # neutral score — let cleanup_matches rank it
                    "source_type": "events",
                    "title": f"[event:{evt['event_type']}] {evt.get('event_time', '')}",
                    "text": evt["summary"],
                    "created_at": evt.get("event_time"),
                })

    except Exception as e:
        log.warning("chronology_timeline_failed", error=str(e))

    return vector_matches


def _route_analysis_parallel(
    interpreted: InterpretedQuery,
    *,
    top_k: int,
    prefetch_k: int,
) -> list[dict]:
    """Analysis with parallel retrieval: main query + alternate queries."""
    queries = [interpreted.normalized_query] + interpreted.alternate_queries[:2]

    all_matches = []
    seen_chunk_ids: set[int] = set()

    def _search(q: str) -> list[dict]:
        return search_chunks(
            query=q,
            top_k=top_k,
            source_types=interpreted.source_types,
            source_names=interpreted.source_names,
            date_from=interpreted.date_from,
            date_to=interpreted.date_to,
            prefetch_k=prefetch_k,
            question_type=interpreted.question_type,
        )

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_search, q): q for q in queries}
        for future in as_completed(futures):
            try:
                matches = future.result()
                for m in matches:
                    cid = m.get("chunk_id")
                    if cid and cid not in seen_chunk_ids:
                        seen_chunk_ids.add(cid)
                        all_matches.append(m)
                    elif not cid:
                        all_matches.append(m)
            except Exception as e:
                q = futures[future]
                log.warning("parallel_search_failed", query=q[:80], error=str(e))

    log.info("parallel_retrieval",
             queries=len(queries),
             total_matches=len(all_matches),
             unique_chunks=len(seen_chunk_ids))

    return all_matches
