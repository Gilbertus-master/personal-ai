from __future__ import annotations

import json
from typing import Any, Optional

from app.db.postgres import get_pg_connection


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _truncate(text: Any, max_len: int = 500) -> Optional[str]:
    if text is None:
        return None
    text = str(text)
    if len(text) <= max_len:
        return text
    return text[:max_len]


def _extract_source_type(match: dict[str, Any]) -> Optional[str]:
    return (
        match.get("source_type")
        or match.get("document_source_type")
        or (match.get("metadata") or {}).get("source_type")
    )


def _extract_source_name(match: dict[str, Any]) -> Optional[str]:
    return (
        match.get("source_name")
        or match.get("document_source_name")
        or (match.get("metadata") or {}).get("source_name")
    )


def _extract_title(match: dict[str, Any]) -> Optional[str]:
    return (
        match.get("title")
        or match.get("document_title")
        or (match.get("metadata") or {}).get("title")
    )


def _extract_created_at(match: dict[str, Any]) -> Optional[str]:
    return (
        match.get("created_at")
        or match.get("document_created_at")
        or (match.get("metadata") or {}).get("created_at")
    )


def _extract_chunk_id(match: dict[str, Any]) -> Optional[int]:
    value = (
        match.get("chunk_id")
        or (match.get("metadata") or {}).get("chunk_id")
    )
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _extract_document_id(match: dict[str, Any]) -> Optional[int]:
    value = (
        match.get("document_id")
        or (match.get("metadata") or {}).get("document_id")
    )
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _extract_score(match: dict[str, Any]) -> Optional[float]:
    value = match.get("score")
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _extract_excerpt(match: dict[str, Any]) -> Optional[str]:
    text = (
        match.get("text")
        or match.get("chunk_text")
        or match.get("excerpt")
        or (match.get("metadata") or {}).get("text")
    )
    return _truncate(text, 500)


def create_session(title: Optional[str] = None, entrypoint: str = "api") -> int:
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (title, entrypoint) VALUES (%s, %s) RETURNING id",
                (title, entrypoint),
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]


def create_ask_run(
    *,
    session_id: Optional[int],
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    interpretation: Optional[dict[str, Any]],
    latency_ms: Optional[int],
    stage_ms: Optional[dict] = None,
    model_used: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: Optional[float] = None,
    error_flag: bool = False,
    error_message: Optional[str] = None,
    cache_hit: bool = False,
) -> int:
    meta = (response_payload or {}).get("meta") or {}
    answer_text = (response_payload or {}).get("answer") or ""
    interp = interpretation or {}

    params = (
        session_id,
        request_payload.get("query"),
        meta.get("normalized_query") or interp.get("normalized_query"),
        meta.get("question_type") or interp.get("question_type"),
        meta.get("analysis_depth") or interp.get("analysis_depth"),
        request_payload.get("top_k", 5),
        interp.get("prefetch_k"),
        interp.get("answer_match_limit"),
        json.dumps(request_payload.get("source_types"), ensure_ascii=False) if request_payload.get("source_types") is not None else None,
        json.dumps(request_payload.get("source_names"), ensure_ascii=False) if request_payload.get("source_names") is not None else None,
        request_payload.get("date_from"),
        request_payload.get("date_to"),
        bool(meta.get("used_fallback", False)),
        _safe_int(meta.get("match_count"), 0),
        answer_text,
        request_payload.get("answer_length", "auto"),
        bool(request_payload.get("allow_quotes", False)),
        bool(request_payload.get("debug", False)),
        latency_ms,
        json.dumps(request_payload, ensure_ascii=False),
        json.dumps(response_payload, ensure_ascii=False),
        # observability columns
        model_used,
        input_tokens,
        output_tokens,
        cost_usd,
        error_flag,
        error_message,
        json.dumps(stage_ms) if stage_ms else None,
        cache_hit,
    )

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ask_runs (
                    session_id, query_text, normalized_query, question_type,
                    analysis_depth, top_k, prefetch_k, answer_match_limit,
                    source_types, source_names, date_from, date_to,
                    used_fallback, match_count, answer_text, answer_length,
                    allow_quotes, debug, latency_ms,
                    raw_request_json, raw_response_json,
                    model_used, input_tokens, output_tokens,
                    cost_usd, error_flag, error_message, stage_ms, cache_hit
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb,
                    %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                )
                RETURNING id
                """,
                params,
            )
            row = cur.fetchone()
        conn.commit()
    return row[0]


def insert_ask_run_matches(ask_run_id: int, matches: list[dict[str, Any]]) -> None:
    if not matches:
        return

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            for idx, match in enumerate(matches, start=1):
                cur.execute(
                    """
                    INSERT INTO ask_run_matches (
                        ask_run_id, chunk_id, document_id, rank_index,
                        score, source_type, source_name, title, created_at, excerpt
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ask_run_id,
                        _extract_chunk_id(match),
                        _extract_document_id(match),
                        idx,
                        _extract_score(match),
                        _extract_source_type(match),
                        _extract_source_name(match),
                        _extract_title(match),
                        _extract_created_at(match),
                        _extract_excerpt(match),
                    ),
                )
        conn.commit()


def persist_ask_run_best_effort(
    *,
    session_id: Optional[int],
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    interpretation: Optional[dict[str, Any]],
    matches: Optional[list[dict[str, Any]]],
    latency_ms: Optional[int],
    stage_ms: Optional[dict] = None,
    model_used: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: Optional[float] = None,
    error_flag: bool = False,
    error_message: Optional[str] = None,
    cache_hit: bool = False,
) -> Optional[int]:
    """
    Best effort:
    - jeśli zapis się uda -> zwraca run_id
    - jeśli nie -> zwraca None i nie wywala całego /ask
    """
    try:
        ask_run_id = create_ask_run(
            session_id=session_id,
            request_payload=request_payload,
            response_payload=response_payload,
            interpretation=interpretation,
            latency_ms=latency_ms,
            stage_ms=stage_ms,
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            error_flag=error_flag,
            error_message=error_message,
            cache_hit=cache_hit,
        )
        insert_ask_run_matches(ask_run_id, matches or [])
        return ask_run_id
    except Exception as exc:
        print(f"[runtime_persistence] WARNING: failed to persist ask run: {exc}")
        return None
