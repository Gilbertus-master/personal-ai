from pathlib import Path
import os
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.api.schemas import AskRequest, AskResponse, MatchItem, SourceItem
from app.retrieval.query_interpreter import interpret_query
from app.retrieval.retriever import search_chunks
from app.retrieval.answering import answer_question
from app.db.runtime_persistence import persist_ask_run_best_effort
from app.retrieval.redaction import redact_matches
from app.retrieval.postprocess import cleanup_matches
from app.retrieval.timeline import query_timeline
from app.retrieval.summaries import (
    generate_daily_summaries,
    generate_weekly_summaries,
    get_summaries,
    AREAS,
)

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

APP_NAME = os.getenv("APP_NAME", "Gilbertus Albans")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_ENV = os.getenv("APP_ENV", "dev")

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)


# =========================
# Local timeline schemas
# =========================

class TimelineRequest(BaseModel):
    event_type: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int = Field(default=20, ge=1, le=500)


class TimelineEvent(BaseModel):
    event_id: int
    event_time: str | None
    event_type: str
    document_id: int
    chunk_id: int
    summary: str
    entities: list[str] = Field(default_factory=list)


class TimelineResponse(BaseModel):
    events: list[TimelineEvent]
    meta: dict[str, Any]


# =========================
# Helpers
# =========================

def model_to_dict(obj: Any) -> dict[str, Any]:
    try:
        return obj.model_dump()
    except AttributeError:
        return obj.dict()


def get_prefetch_k(question_type: str, analysis_depth: str) -> int:
    base = {
        "retrieval": 40,
        "summary": 60,
        "analysis": 90,
        "chronology": 120,
    }.get(question_type, 60)

    if analysis_depth == "high":
        base = int(base * 1.25)
    elif analysis_depth == "low":
        base = int(base * 0.75)

    return max(base, 20)


def get_answer_match_limit(question_type: str, analysis_depth: str) -> int:
    base = {
        "retrieval": 12,
        "summary": 18,
        "analysis": 24,
        "chronology": 24,
    }.get(question_type, 18)

    if analysis_depth == "high":
        base = int(base * 1.25)
    elif analysis_depth == "low":
        base = int(base * 0.75)

    return max(base, 6)


def sort_matches_for_question_type(matches: list[dict[str, Any]], question_type: str) -> list[dict[str, Any]]:
    if question_type == "chronology":
        return sorted(
            matches,
            key=lambda m: (m.get("created_at") is None, m.get("created_at") or "9999-12-31"),
        )
    return matches


def build_sources_from_matches(matches: list[dict[str, Any]]) -> list[SourceItem]:
    seen = set()
    sources: list[SourceItem] = []

    for m in matches:
        key = (
            m.get("document_id"),
            m.get("title"),
            m.get("source_type"),
            m.get("source_name"),
            m.get("created_at"),
        )
        if key in seen:
            continue
        seen.add(key)

        sources.append(
            SourceItem(
                document_id=m.get("document_id"),
                title=m.get("title"),
                source_type=m.get("source_type"),
                source_name=m.get("source_name"),
                created_at=m.get("created_at"),
            )
        )

    return sources


def build_debug_matches(matches: list[dict[str, Any]]) -> list[MatchItem]:
    response_matches: list[MatchItem] = []

    for m in matches:
        response_matches.append(
            MatchItem(
                chunk_id=m.get("chunk_id"),
                document_id=m.get("document_id"),
                score=float(m.get("score", 0.0)),
                source_type=m.get("source_type"),
                source_name=m.get("source_name"),
                title=m.get("title"),
                created_at=str(m.get("created_at")) if m.get("created_at") is not None else None,
                text=str(m.get("text") or m.get("chunk_text") or ""),
            )
        )

    return response_matches


def run_timeline_query(
    event_type: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    return query_timeline(
        event_type=event_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


# =========================
# Basic endpoints
# =========================

@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "env": APP_ENV,
    }


@app.get("/version")
def version() -> dict[str, Any]:
    return {
        "app_name": APP_NAME,
        "version": APP_VERSION,
    }


# =========================
# Ask endpoint
# =========================

@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    started_at = time.time()
    request_payload = model_to_dict(request)

    interpreted = interpret_query(
        query=request.query,
        source_types=request.source_types,
        source_names=request.source_names,
        date_from=request.date_from,
        date_to=request.date_to,
        mode=request.mode,
    )

    prefetch_k = get_prefetch_k(
        interpreted.question_type,
        interpreted.analysis_depth,
    )

    answer_match_limit = get_answer_match_limit(
        interpreted.question_type,
        interpreted.analysis_depth,
    )

    final_match_limit = max(request.top_k, min(answer_match_limit, request.top_k * 3))

    matches = search_chunks(
        query=interpreted.normalized_query,
        top_k=answer_match_limit,
        source_types=interpreted.source_types,
        source_names=interpreted.source_names,
        date_from=interpreted.date_from,
        date_to=interpreted.date_to,
        prefetch_k=prefetch_k,
        question_type=interpreted.question_type,
    )

    used_fallback = False

    if not matches:
        used_fallback = True
        matches = search_chunks(
            query=request.query,
            top_k=answer_match_limit,
            source_types=request.source_types,
            source_names=request.source_names,
            date_from=request.date_from,
            date_to=request.date_to,
            prefetch_k=prefetch_k,
            question_type=interpreted.question_type,
        )

    if not matches:
        latency_ms = int((time.time() - started_at) * 1000)

        response_meta = {
            "question_type": interpreted.question_type,
            "analysis_depth": interpreted.analysis_depth,
            "used_fallback": used_fallback,
            "retrieved_count": 0,
            "used_for_answer_count": 0,
            "redacted_count": 0,
            "cleanup_input_count": 0,
            "cleanup_output_count": 0,
            "cleanup_score_filtered_out": 0,
            "cleanup_dedup_filtered_out": 0,
            "cleanup_document_capped_out": 0,
            "answer_match_limit": answer_match_limit,
            "final_match_limit": final_match_limit,
            "normalized_query": interpreted.normalized_query,
            "date_from": interpreted.date_from,
            "date_to": interpreted.date_to,
            "answer_style": request.answer_style,
            "answer_length": request.answer_length,
            "allow_quotes": request.allow_quotes,
            "debug": request.debug,
        }

        response_payload = {
            "answer": "Nie znalazłem wystarczająco trafnego kontekstu dla tego pytania.",
            "sources": [] if request.debug else None,
            "matches": [] if request.debug else None,
            "meta": response_meta,
        }

        run_id = persist_ask_run_best_effort(
            session_id=None,
            request_payload=request_payload,
            response_payload=response_payload,
            interpretation={
                "normalized_query": interpreted.normalized_query,
                "question_type": interpreted.question_type,
                "analysis_depth": interpreted.analysis_depth,
                "prefetch_k": prefetch_k,
                "answer_match_limit": answer_match_limit,
            },
            matches=[],
            latency_ms=latency_ms,
        )

        return AskResponse(
            answer=response_payload["answer"],
            sources=response_payload["sources"],
            matches=response_payload["matches"],
            meta=response_meta,
            run_id=run_id,
        )

    matches = sort_matches_for_question_type(matches, interpreted.question_type)
    retrieved_count = len(matches)

    cleaned_matches, cleanup_stats = cleanup_matches(
        matches,
        normalized_query=interpreted.normalized_query,
        top_k=final_match_limit,
        max_per_document=2,
        min_score=None,
    )

    matches_for_answer = cleaned_matches
    used_for_answer_count = len(matches_for_answer)

    redacted_matches_for_answer, redacted_count = redact_matches(matches_for_answer)

    answer = answer_question(
        query=request.query,
        matches=redacted_matches_for_answer,
        question_type=interpreted.question_type,
        analysis_depth=interpreted.analysis_depth,
        include_sources=request.include_sources,
        answer_style=request.answer_style,
        answer_length=request.answer_length,
        allow_quotes=request.allow_quotes,
    )

    response_sources = build_sources_from_matches(redacted_matches_for_answer) if request.debug else None
    response_matches = build_debug_matches(redacted_matches_for_answer) if request.debug else None

    response_meta = {
        "question_type": interpreted.question_type,
        "analysis_depth": interpreted.analysis_depth,
        "used_fallback": used_fallback,
        "retrieved_count": retrieved_count,
        "used_for_answer_count": used_for_answer_count,
        "redacted_count": redacted_count,
        "cleanup_input_count": cleanup_stats["input_count"],
        "cleanup_output_count": cleanup_stats["output_count"],
        "cleanup_score_filtered_out": cleanup_stats["score_filtered_out"],
        "cleanup_dedup_filtered_out": cleanup_stats["dedup_filtered_out"],
        "cleanup_document_capped_out": cleanup_stats["document_capped_out"],
        "answer_match_limit": answer_match_limit,
        "final_match_limit": final_match_limit,
        "normalized_query": interpreted.normalized_query,
        "date_from": interpreted.date_from,
        "date_to": interpreted.date_to,
        "answer_style": request.answer_style,
        "answer_length": request.answer_length,
        "allow_quotes": request.allow_quotes,
        "debug": request.debug,
    }

    latency_ms = int((time.time() - started_at) * 1000)

    response_payload = {
        "answer": answer,
        "sources": [model_to_dict(s) for s in response_sources] if response_sources else None,
        "matches": [model_to_dict(m) for m in response_matches] if response_matches else None,
        "meta": response_meta,
    }

    run_id = persist_ask_run_best_effort(
        session_id=None,
        request_payload=request_payload,
        response_payload=response_payload,
        interpretation={
            "normalized_query": interpreted.normalized_query,
            "question_type": interpreted.question_type,
            "analysis_depth": interpreted.analysis_depth,
            "prefetch_k": prefetch_k,
            "answer_match_limit": answer_match_limit,
        },
        matches=matches_for_answer,
        latency_ms=latency_ms,
    )

    return AskResponse(
        answer=answer,
        sources=response_sources,
        matches=response_matches,
        meta=response_meta,
        run_id=run_id,
    )


# =========================
# Timeline endpoint
# =========================

@app.post("/timeline", response_model=TimelineResponse)
def timeline(request: TimelineRequest) -> TimelineResponse:
    started_at = time.time()

    events_raw = run_timeline_query(
        event_type=request.event_type,
        date_from=request.date_from,
        date_to=request.date_to,
        limit=request.limit,
    )

    events = [
        TimelineEvent(
            event_id=int(e["event_id"]),
            event_time=e.get("event_time"),
            event_type=e["event_type"],
            document_id=int(e["document_id"]),
            chunk_id=int(e["chunk_id"]),
            summary=e["summary"],
            entities=list(e.get("entities", [])),
        )
        for e in events_raw
    ]

    latency_ms = int((time.time() - started_at) * 1000)

    meta = {
        "event_type": request.event_type,
        "date_from": request.date_from,
        "date_to": request.date_to,
        "limit": request.limit,
        "count": len(events),
        "latency_ms": latency_ms,
    }

    return TimelineResponse(
        events=events,
        meta=meta,
    )


# =========================
# Summary endpoints
# =========================

class SummaryGenerateRequest(BaseModel):
    date: str = Field(..., description="Date for daily (YYYY-MM-DD) or week start for weekly")
    summary_type: str = Field(default="daily", description="daily or weekly")
    areas: list[str] | None = Field(default=None, description="Areas to summarize, default all")


class SummaryItem(BaseModel):
    summary_id: int | None = None
    summary_type: str
    area: str | None = None
    period: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    status: str | None = None
    chunks_used: int | None = None
    events_used: int | None = None
    text: str | None = None


class SummaryGenerateResponse(BaseModel):
    results: list[SummaryItem]
    meta: dict[str, Any]


class SummaryQueryRequest(BaseModel):
    summary_type: str | None = None
    area: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class SummaryQueryResponse(BaseModel):
    summaries: list[SummaryItem]
    meta: dict[str, Any]


@app.post("/summary/generate", response_model=SummaryGenerateResponse)
def summary_generate(request: SummaryGenerateRequest) -> SummaryGenerateResponse:
    started_at = time.time()

    if request.summary_type == "weekly":
        results = generate_weekly_summaries(request.date, areas=request.areas)
    else:
        results = generate_daily_summaries(request.date, areas=request.areas)

    items = [SummaryItem(**r) for r in results]
    latency_ms = int((time.time() - started_at) * 1000)

    return SummaryGenerateResponse(
        results=items,
        meta={
            "summary_type": request.summary_type,
            "date": request.date,
            "areas": request.areas or AREAS,
            "generated_count": sum(1 for r in results if r.get("status") == "generated"),
            "no_data_count": sum(1 for r in results if r.get("status") == "no_data"),
            "latency_ms": latency_ms,
        },
    )


@app.post("/summary/query", response_model=SummaryQueryResponse)
def summary_query(request: SummaryQueryRequest) -> SummaryQueryResponse:
    started_at = time.time()

    summaries = get_summaries(
        summary_type=request.summary_type,
        area=request.area,
        date_from=request.date_from,
        date_to=request.date_to,
        limit=request.limit,
    )

    items = [SummaryItem(**s) for s in summaries]
    latency_ms = int((time.time() - started_at) * 1000)

    return SummaryQueryResponse(
        summaries=items,
        meta={
            "count": len(items),
            "latency_ms": latency_ms,
        },
    )