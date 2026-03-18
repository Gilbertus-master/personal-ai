from __future__ import annotations

import json
import time
from typing import Any, Optional

from app.ingestion.common.db import _run_sql


def _sql_quote(value: Any) -> str:
    """
    Zamienia wartość Pythona na bezpieczny literał SQL.
    """
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, (int, float)):
        return str(value)

    text = str(value)
    text = text.replace("'", "''")
    return f"'{text}'"


def _sql_json(value: Any) -> str:
    """
    Zwraca literał SQL typu jsonb.
    """
    if value is None:
        return "NULL"

    json_text = json.dumps(value, ensure_ascii=False)
    json_text = json_text.replace("'", "''")
    return f"'{json_text}'::jsonb"


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
    sql = f"""
    INSERT INTO sessions (title, entrypoint)
    VALUES ({_sql_quote(title)}, {_sql_quote(entrypoint)})
    RETURNING id;
    """
    result = _run_sql(sql)
    return int(result.strip())


def create_ask_run(
    *,
    session_id: Optional[int],
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    interpretation: Optional[dict[str, Any]],
    latency_ms: Optional[int],
) -> int:
    meta = (response_payload or {}).get("meta") or {}
    answer_text = (response_payload or {}).get("answer") or ""

    sql = f"""
    INSERT INTO ask_runs (
        session_id,
        query_text,
        normalized_query,
        question_type,
        analysis_depth,
        top_k,
        prefetch_k,
        answer_match_limit,
        source_types,
        source_names,
        date_from,
        date_to,
        used_fallback,
        match_count,
        answer_text,
        answer_length,
        allow_quotes,
        debug,
        latency_ms,
        raw_request_json,
        raw_response_json
    )
    VALUES (
        {_sql_quote(session_id)},
        {_sql_quote(request_payload.get("query"))},
        {_sql_quote(meta.get("normalized_query") or (interpretation or {}).get("normalized_query"))},
        {_sql_quote(meta.get("question_type") or (interpretation or {}).get("question_type"))},
        {_sql_quote(meta.get("analysis_depth") or (interpretation or {}).get("analysis_depth"))},
        {_sql_quote(request_payload.get("top_k", 5))},
        {_sql_quote((interpretation or {}).get("prefetch_k"))},
        {_sql_quote((interpretation or {}).get("answer_match_limit"))},
        {_sql_json(request_payload.get("source_types"))},
        {_sql_json(request_payload.get("source_names"))},
        {_sql_quote(request_payload.get("date_from"))},
        {_sql_quote(request_payload.get("date_to"))},
        {_sql_quote(bool(meta.get("used_fallback", False)))},
        {_sql_quote(_safe_int(meta.get("match_count"), 0))},
        {_sql_quote(answer_text)},
        {_sql_quote(request_payload.get("answer_length", "auto"))},
        {_sql_quote(bool(request_payload.get("allow_quotes", False)))},
        {_sql_quote(bool(request_payload.get("debug", False)))},
        {_sql_quote(latency_ms)},
        {_sql_json(request_payload)},
        {_sql_json(response_payload)}
    )
    RETURNING id;
    """
    result = _run_sql(sql)
    return int(result.strip())


def insert_ask_run_matches(ask_run_id: int, matches: list[dict[str, Any]]) -> None:
    if not matches:
        return

    values_sql: list[str] = []

    for idx, match in enumerate(matches, start=1):
        row_sql = f"""(
            {_sql_quote(ask_run_id)},
            {_sql_quote(_extract_chunk_id(match))},
            {_sql_quote(_extract_document_id(match))},
            {_sql_quote(idx)},
            {_sql_quote(_extract_score(match))},
            {_sql_quote(_extract_source_type(match))},
            {_sql_quote(_extract_source_name(match))},
            {_sql_quote(_extract_title(match))},
            {_sql_quote(_extract_created_at(match))},
            {_sql_quote(_extract_excerpt(match))}
        )"""
        values_sql.append(row_sql)

    sql = f"""
    INSERT INTO ask_run_matches (
        ask_run_id,
        chunk_id,
        document_id,
        rank_index,
        score,
        source_type,
        source_name,
        title,
        created_at,
        excerpt
    )
    VALUES
    {",\n".join(values_sql)};
    """

    _run_sql(sql)


def persist_ask_run_best_effort(
    *,
    session_id: Optional[int],
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    interpretation: Optional[dict[str, Any]],
    matches: Optional[list[dict[str, Any]]],
    latency_ms: Optional[int],
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
        )
        insert_ask_run_matches(ask_run_id, matches or [])
        return ask_run_id
    except Exception as exc:
        print(f"[runtime_persistence] WARNING: failed to persist ask run: {exc}")
        return None
    