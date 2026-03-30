"""
Shared business-only RAG pipeline for Gilbertus Albans.

Used by both presentation.py (/presentation/ask) and teams_bot.py (Teams webhook)
so that retrieval logic — prefetch_k, min_score, source filtering — stays in one place.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import structlog

from app.db.postgres import get_pg_connection
from app.retrieval.query_interpreter import interpret_query
from app.retrieval.retriever import search_chunks
from app.retrieval.answering import answer_question
from app.retrieval.redaction import redact_matches
from app.retrieval.postprocess import cleanup_matches

log = structlog.get_logger("business_pipeline")

# ─── Source type allow/block lists ───────────────────────────────────────────

ALLOWED_SOURCE_TYPES: frozenset[str] = frozenset({
    "email",
    "teams",
    "spreadsheet",
    "document",
    "email_attachment",
    "audio_transcript",
})

BLOCKED_SOURCE_TYPES: frozenset[str] = frozenset({
    "whatsapp",
    "chatgpt",
    "whatsapp_live",
})

_PREFETCH_K = 50
_ANSWER_MATCH_LIMIT = 14

# ─── Filter helpers ───────────────────────────────────────────────────────────

def enforce_source_filter(source_types: list[str] | None) -> list[str]:
    """
    Ensure only ALLOWED source types are queried.
    If caller passes source_types, intersect with allowed set.
    If None, return the full allowed list.
    """
    if source_types:
        filtered = [st for st in source_types if st in ALLOWED_SOURCE_TYPES]
        if not filtered:
            log.warning(
                "business_pipeline.source_filter_fallback",
                requested=source_types,
            )
            return list(ALLOWED_SOURCE_TYPES)
        return filtered
    return list(ALLOWED_SOURCE_TYPES)


def validate_no_blocked_sources(matches: list[dict]) -> list[dict]:
    """
    Defence-in-depth: strip any match whose source_type leaked through.
    This should never happen if the retriever respects source_types,
    but we enforce it as a hard safety layer.
    """
    safe = []
    for m in matches:
        st = (m.get("source_type") or "").lower()
        if st in BLOCKED_SOURCE_TYPES:
            log.warning(
                "business_pipeline.blocked_source_leaked",
                source_type=st,
                chunk_id=m.get("chunk_id"),
            )
            continue
        safe.append(m)
    return safe


# ─── Shared RAG pipeline ──────────────────────────────────────────────────────

def run_business_rag(
    query: str,
    system_addendum: str,
    conversation_context: str = "",
    top_k: int = 8,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """
    Run the business-only RAG pipeline.

    Parameters
    ----------
    query:                Raw user query.
    system_addendum:      Persona/instruction text prepended to the query for the LLM.
    conversation_context: Optional prior-turn context string.
    top_k:                Max cleaned matches passed to the answer model after retrieval.
                          Retrieval always fetches up to answer_match_limit=14 chunks from
                          the vector store; cleanup_matches then trims to min(top_k, 14).
    date_from / date_to:  Optional ISO-8601 date range strings for retrieval.

    Returns
    -------
    dict with keys:
        answer           – str
        match_count      – int   (redacted matches sent to LLM)
        question_type    – str
        source_types_used – list[str]
        latency_ms       – int
    """
    started_at = time.time()

    # Cache check (TTL 1 h) — skip LLM cost on repeated queries
    cache_key = hashlib.md5(
        json.dumps([query.strip().lower(), date_from, date_to], sort_keys=True).encode()
    ).hexdigest()
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT answer_text, meta FROM answer_cache WHERE cache_key = %s AND expires_at > NOW()",
                    (cache_key,),
                )
                rows = cur.fetchall()
                if rows:
                    answer_text, meta_json = rows[0]
                    cached_meta = meta_json if isinstance(meta_json, dict) else {}
                    log.info("business_pipeline.cache_hit", cache_key=cache_key)
                    return {
                        "answer": answer_text,
                        "match_count": cached_meta.get("match_count", 0),
                        "question_type": cached_meta.get("question_type", "unknown"),
                        "source_types_used": cached_meta.get("source_types_used", []),
                        "latency_ms": int((time.time() - started_at) * 1000),
                        "cached": True,
                    }
    except Exception:
        pass

    safe_source_types = enforce_source_filter(None)

    try:
        interpreted = interpret_query(
            query=query,
            source_types=safe_source_types,
            source_names=None,
            date_from=date_from,
            date_to=date_to,
            mode="auto",
        )

        interpreted_source_types = enforce_source_filter(interpreted.source_types)

        prefetch_k = _PREFETCH_K
        answer_match_limit = _ANSWER_MATCH_LIMIT

        matches = search_chunks(
            query=interpreted.normalized_query,
            top_k=answer_match_limit,
            source_types=interpreted_source_types,
            source_names=interpreted.source_names,
            date_from=interpreted.date_from,
            date_to=interpreted.date_to,
            prefetch_k=prefetch_k,
            question_type=interpreted.question_type,
        )

        # Fallback: raw query with original date range
        if not matches:
            matches = search_chunks(
                query=query,
                top_k=answer_match_limit,
                source_types=safe_source_types,
                source_names=None,
                date_from=date_from,
                date_to=date_to,
                prefetch_k=prefetch_k,
                question_type=interpreted.question_type,
            )

        # Defence-in-depth: strip any blocked sources
        matches = validate_no_blocked_sources(matches)

        no_context_answer = "Nie znalazlem wystarczajaco trafnego kontekstu biznesowego dla tego pytania."
        if not matches:
            return {
                "answer": no_context_answer,
                "match_count": 0,
                "question_type": interpreted.question_type,
                "source_types_used": interpreted_source_types,
                "latency_ms": int((time.time() - started_at) * 1000),
            }

        cleaned_matches, _ = cleanup_matches(
            matches,
            normalized_query=interpreted.normalized_query,
            top_k=min(top_k, answer_match_limit),
            max_per_document=2,
            min_score=None,
        )

        redacted_matches, _ = redact_matches(cleaned_matches)

        answer = answer_question(
            query=f"[KONTEKST SYSTEMOWY: {system_addendum}]\n\n{query}",
            matches=redacted_matches,
            question_type=interpreted.question_type,
            analysis_depth=interpreted.analysis_depth,
            include_sources=False,
            answer_style="auto",
            answer_length="medium",
            allow_quotes=True,
            conversation_context=conversation_context,
        )

        latency_ms = int((time.time() - started_at) * 1000)
        log.info(
            "business_pipeline.answered",
            latency_ms=latency_ms,
            match_count=len(redacted_matches),
            question_type=interpreted.question_type,
        )

        result = {
            "answer": answer,
            "match_count": len(redacted_matches),
            "question_type": interpreted.question_type,
            "source_types_used": interpreted_source_types,
            "latency_ms": latency_ms,
        }
    except Exception:
        log.error("business_pipeline.error", exc_info=True, query=query)
        raise

    # Persist to cache for 1 h
    try:
        meta = {
            "match_count": result["match_count"],
            "question_type": result["question_type"],
            "source_types_used": result["source_types_used"],
        }
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO answer_cache (cache_key, query_text, answer_text, meta, expires_at)
                       VALUES (%s, %s, %s, %s::jsonb, NOW() + INTERVAL '1 hour')
                       ON CONFLICT (cache_key) DO UPDATE
                       SET answer_text = EXCLUDED.answer_text,
                           meta        = EXCLUDED.meta,
                           expires_at  = EXCLUDED.expires_at""",
                    (cache_key, query, answer, json.dumps(meta, default=str)),
                )
            conn.commit()
    except Exception:
        pass

    return result
