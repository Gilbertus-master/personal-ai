from pathlib import Path
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.schemas import AskRequest, AskResponse, MatchItem, SourceItem
from app.retrieval.query_interpreter import interpret_query
from app.retrieval.retriever import search_chunks
from app.retrieval.answering import answer_question
from app.db.runtime_persistence import persist_ask_run_best_effort

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

APP_NAME = os.getenv("APP_NAME", "Gilbertus Albans")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_ENV = os.getenv("APP_ENV", "dev")

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)


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


def sort_matches_for_question_type(matches: list[dict], question_type: str) -> list[dict]:
    if question_type == "chronology":
        return sorted(
            matches,
            key=lambda m: (m.get("created_at") is None, m.get("created_at") or "9999-12-31"),
        )
    return matches


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "env": APP_ENV,
    }


@app.get("/version")
def version() -> dict:
    return {
        "app_name": APP_NAME,
        "version": APP_VERSION,
    }


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    started_at = time.time()

    try:
        request_payload = request.model_dump()
    except AttributeError:
        request_payload = request.dict()

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
            "match_count": 0,
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
    matches_for_answer = matches[:answer_match_limit]

    answer = answer_question(
        query=request.query,
        matches=matches_for_answer,
        question_type=interpreted.question_type,
        analysis_depth=interpreted.analysis_depth,
        include_sources=request.include_sources,
        answer_style=request.answer_style,
        answer_length=request.answer_length,
        allow_quotes=request.allow_quotes,
    )

    seen = set()
    sources = []
    for m in matches_for_answer:
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

    response_sources = sources if request.debug else None

    response_matches = None
    if request.debug:
        response_matches = []
        for m in matches_for_answer:
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

    response_meta = {
        "question_type": interpreted.question_type,
        "analysis_depth": interpreted.analysis_depth,
        "used_fallback": used_fallback,
        "match_count": len(matches_for_answer),
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
        "sources": [s.dict() for s in response_sources] if response_sources else None,
        "matches": [m.dict() for m in response_matches] if response_matches else None,
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