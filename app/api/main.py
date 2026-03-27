from pathlib import Path
import os
import time
import logging
from datetime import datetime, timezone
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
from app.retrieval.morning_brief import generate_morning_brief
from app.analysis.correlation import run_correlation, person_event_profile
from app.analysis.inefficiency import generate_inefficiency_report
from app.analysis.opportunity_detector import run_opportunity_scan
from app.evaluation.data_collector import collect_person_data
from app.evaluation.evaluator import evaluate_person
from app.retrieval.alerts import get_alerts, run_alerts_check
from app.api.plaud_webhook import router as plaud_router
from app.api.voice import router as voice_router
from app.api.decisions import router as decisions_router
from app.api.insights import router as insights_router
from app.api.presentation import router as presentation_router
from app.api.relationships import router as relationships_router
from app.api.teams_bot import router as teams_router
from app.db.postgres import get_pg_connection

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

APP_NAME = os.getenv("APP_NAME", "Gilbertus Albans")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_ENV = os.getenv("APP_ENV", "dev")

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)

app.include_router(plaud_router)
app.include_router(decisions_router)
app.include_router(insights_router)
app.include_router(presentation_router)
app.include_router(relationships_router)
app.include_router(teams_router)
app.include_router(voice_router)


# =========================
# Evaluation endpoint
# =========================

class EvaluateRequest(BaseModel):
    person_slug: str = Field(description="Person slug or 'first-last' name")
    date_from: str | None = Field(default=None, description="YYYY-MM-DD")
    date_to: str | None = Field(default=None, description="YYYY-MM-DD")

@app.post("/evaluate")
def evaluate(req: EvaluateRequest):
    started = time.time()
    data = collect_person_data(
        person_slug=req.person_slug,
        date_from=req.date_from,
        date_to=req.date_to,
    )
    if "error" in data:
        return {"error": data["error"]}

    result = evaluate_person(data)
    result["latency_ms"] = int((time.time() - started) * 1000)
    return result


# =========================
# Scorecard endpoint
# =========================

@app.get("/scorecard/{person_slug}")
def scorecard(person_slug: str):
    """Employee scorecard — aggregated view of a person's data, events, anomalies."""
    from app.db.postgres import get_pg_connection

    name_parts = person_slug.replace("-", " ").split()
    first = name_parts[0] if name_parts else ""
    last = name_parts[-1] if len(name_parts) > 1 else ""

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # Find person
            cur.execute("""
                SELECT p.id, p.first_name, p.last_name, p.entity_id,
                       r.person_role, r.organization, r.status, r.sentiment
                FROM people p
                LEFT JOIN relationships r ON r.person_id = p.id
                WHERE LOWER(p.first_name) = LOWER(%s) AND LOWER(p.last_name) = LOWER(%s)
                LIMIT 1
            """, (first, last))
            rows = cur.fetchall()
            if not rows:
                return {"error": f"Person not found: {person_slug}"}

            pid, fn, ln, eid, role, org, status, sentiment = rows[0]

            # Data volume
            chunks = 0
            events_count = 0
            if eid:
                cur.execute("SELECT COUNT(*) FROM chunk_entities WHERE entity_id = %s", (eid,))
                chunks = cur.fetchall()[0][0]
                cur.execute("SELECT COUNT(*) FROM event_entities WHERE entity_id = %s", (eid,))
                events_count = cur.fetchall()[0][0]

            # Recent events (last 30 days)
            recent = []
            if eid:
                cur.execute("""
                    SELECT e.event_type, e.event_time, e.summary
                    FROM events e JOIN event_entities ee ON ee.event_id = e.id
                    WHERE ee.entity_id = %s AND e.event_time > NOW() - INTERVAL '30 days'
                    ORDER BY e.event_time DESC LIMIT 10
                """, (eid,))
                recent = [{"type": r[0], "time": str(r[1]) if r[1] else None, "summary": r[2]} for r in cur.fetchall()]

            # Open loops
            cur.execute("""
                SELECT description FROM relationship_open_loops
                WHERE person_id = %s AND status = 'open'
            """, (pid,))
            loops = [r[0] for r in cur.fetchall()]

    # Event profile
    profile = person_event_profile(f"{fn} {ln}", months=3)

    return {
        "person": {"name": f"{fn} {ln}", "role": role, "org": org, "status": status, "sentiment": sentiment},
        "data_volume": {"chunks": chunks, "events": events_count},
        "recent_events_30d": recent,
        "open_loops": loops,
        "event_profile_3m": profile.get("event_type_breakdown", {}),
        "weekly_activity": profile.get("weekly_data", [])[:8],
    }


# =========================
# Correlation endpoint
# =========================

@app.post("/opportunities/scan")
def scan_opportunities(hours: int = 2):
    return run_opportunity_scan(hours=hours, notify=False)

@app.get("/opportunities")
def list_opportunities(status: str = "new", limit: int = 20):
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, opportunity_type, description, estimated_value_pln,
                       estimated_effort_hours, roi_score, confidence, status, created_at
                FROM opportunities WHERE status = %s
                ORDER BY roi_score DESC NULLS LAST LIMIT %s
            """, (status, limit))
            return [{"id": r[0], "type": r[1], "description": r[2], "value_pln": float(r[3]) if r[3] else 0,
                     "effort_hours": float(r[4]) if r[4] else 0, "roi": float(r[5]) if r[5] else 0,
                     "confidence": r[6], "status": r[7], "created": str(r[8])} for r in cur.fetchall()]

@app.get("/inefficiency")
def inefficiency():
    return generate_inefficiency_report()


class CorrelationRequest(BaseModel):
    correlation_type: str = Field(default="report", description="temporal, person, anomaly, or report")
    event_type_a: str | None = None
    event_type_b: str | None = None
    person: str | None = None
    window: str = "week"

@app.post("/correlate")
def correlate(req: CorrelationRequest):
    result = run_correlation(
        correlation_type=req.correlation_type,
        event_type_a=req.event_type_a,
        event_type_b=req.event_type_b,
        person=req.person,
        window=req.window,
    )
    return result


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
        "retrieval": 30,
        "summary": 50,
        "analysis": 70,
        "chronology": 100,
    }.get(question_type, 50)

    if analysis_depth == "high":
        base = int(base * 1.25)
    elif analysis_depth == "low":
        base = int(base * 0.75)

    return max(base, 20)


def get_answer_match_limit(question_type: str, analysis_depth: str) -> int:
    base = {
        "retrieval": 8,
        "summary": 14,
        "analysis": 18,
        "chronology": 20,
    }.get(question_type, 14)

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
# Status endpoint
# =========================

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
WHISPER_URL = os.getenv("WHISPER_URL", "http://127.0.0.1:9090")

CRON_JOBS = [
    {"schedule": "0 3 * * *",           "name": "backup_db",        "description": "Database backup"},
    {"schedule": "20 3 * * *",          "name": "prune_backups",    "description": "Prune old backups"},
    {"schedule": "0 7,11,15,19,23 * * *", "name": "backup_db",     "description": "Database backup (daytime)"},
    {"schedule": "@reboot",             "name": "pg_auto_restore",  "description": "Auto-restore Postgres on boot"},
    {"schedule": "*/5 * * * *",         "name": "index_chunks",     "description": "Auto-embed new chunks"},
    {"schedule": "*/15 * * * *",        "name": "plaud_monitor",    "description": "Plaud audio monitor"},
    {"schedule": "*/5 * * * *",         "name": "live_ingest",      "description": "WhatsApp live ingest"},
    {"schedule": "0 7 * * *",           "name": "morning_brief",    "description": "Generate morning brief"},
    {"schedule": "0 * * * *",           "name": "extract_entities", "description": "Entity extraction (hourly)"},
    {"schedule": "30 * * * *",          "name": "extract_events",   "description": "Event extraction (hourly)"},
]


def _check_service(url: str, timeout: float = 3.0) -> dict[str, Any]:
    """Check if an HTTP service is responding."""
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status": "ok", "http_status": resp.status}
    except urllib.error.URLError as e:
        return {"status": "error", "error": str(e.reason)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _get_last_backup_timestamp() -> str | None:
    """Find the newest backup folder in backups/db/."""
    backup_dir = BASE_DIR / "backups" / "db"
    if not backup_dir.is_dir():
        return None
    folders = sorted(
        (d.name for d in backup_dir.iterdir() if d.is_dir()),
        reverse=True,
    )
    if not folders:
        return None
    # Folder names look like 2026-03-15_13-24-15
    raw = folders[0]
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d_%H-%M-%S")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return raw


@app.get("/status")
def system_status() -> dict[str, Any]:
    """
    System status dashboard — no auth required.
    Returns DB stats, embedding status, source breakdown,
    last backup, service health, and cron jobs.
    """
    started_at = time.time()
    result: dict[str, Any] = {}

    # ── 1. Database stats ──────────────────────────────────────────────
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM documents")
                document_count = cur.fetchone()[0]

                cur.execute("SELECT count(*) FROM chunks")
                chunk_count = cur.fetchone()[0]

                cur.execute("SELECT count(*) FROM entities")
                entity_count = cur.fetchone()[0]

                cur.execute("SELECT count(*) FROM events")
                event_count = cur.fetchone()[0]

                cur.execute("SELECT count(*) FROM summaries")
                summary_count = cur.fetchone()[0]

                # insights table may not exist yet
                try:
                    cur.execute("SELECT count(*) FROM insights")
                    insight_count = cur.fetchone()[0]
                except Exception:
                    conn.rollback()
                    insight_count = None

                try:
                    cur.execute("SELECT count(*) FROM alerts")
                    alert_count = cur.fetchone()[0]
                except Exception:
                    conn.rollback()
                    alert_count = None

        result["db"] = {
            "documents": document_count,
            "chunks": chunk_count,
            "entities": entity_count,
            "events": event_count,
            "insights": insight_count,
            "summaries": summary_count,
            "alerts": alert_count,
        }
    except Exception as e:
        logger.warning("Status: DB stats failed: %s", e)
        result["db"] = {"error": str(e)}

    # ── 2. Embedding status ────────────────────────────────────────────
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM chunks")
                total = cur.fetchone()[0]

                cur.execute(
                    "SELECT count(*) FROM chunks WHERE embedding_id IS NOT NULL"
                )
                done = cur.fetchone()[0]

        result["embeddings"] = {
            "total": total,
            "done": done,
            "pending": total - done,
        }
    except Exception as e:
        logger.warning("Status: embedding stats failed: %s", e)
        result["embeddings"] = {"error": str(e)}

    # ── 3. Source breakdown ────────────────────────────────────────────
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT s.source_type,
                           count(d.id)                    AS doc_count,
                           max(d.created_at)::text        AS newest_date
                    FROM documents d
                    JOIN sources s ON s.id = d.source_id
                    GROUP BY s.source_type
                    ORDER BY doc_count DESC
                """)
                rows = cur.fetchall()

        result["sources"] = [
            {
                "source_type": row[0],
                "document_count": row[1],
                "newest_date": row[2],
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning("Status: source breakdown failed: %s", e)
        result["sources"] = {"error": str(e)}

    # ── 4. Last backup ─────────────────────────────────────────────────
    result["last_backup"] = _get_last_backup_timestamp()

    # ── 5. Service health ──────────────────────────────────────────────
    pg_status: dict[str, Any]
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        pg_status = {"status": "ok"}
    except Exception as e:
        pg_status = {"status": "error", "error": str(e)}

    result["services"] = {
        "postgres": pg_status,
        "qdrant": _check_service(QDRANT_URL),
        "whisper": _check_service(WHISPER_URL),
    }

    # ── 6. Cron jobs ──────────────────────────────────────────────────
    result["cron_jobs"] = CRON_JOBS

    latency_ms = int((time.time() - started_at) * 1000)
    result["latency_ms"] = latency_ms

    return result


# =========================
# Ask endpoint
# =========================

def _apply_channel_defaults(request: AskRequest) -> AskRequest:
    """Override defaults for specific channels (e.g. WhatsApp needs fast, short answers)."""
    if request.channel == "whatsapp":
        # Only override if user didn't explicitly set these
        if request.answer_length == "long":
            request.answer_length = "short"
        if request.top_k == 8:  # still at default
            request.top_k = 5
    return request


def _cache_key_for_ask(query: str, source_types, date_from, date_to) -> str:
    import hashlib
    import json
    raw = json.dumps([query.strip().lower(), source_types, date_from, date_to], sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def _check_answer_cache(cache_key: str):
    """Check if answer is cached and not expired."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT answer_text, meta FROM answer_cache WHERE cache_key = %s AND expires_at > NOW() LIMIT 1",
                    (cache_key,),
                )
                rows = cur.fetchall()
                return rows[0] if rows else None
    except Exception:
        return None


def _save_answer_cache(cache_key: str, query: str, answer: str, meta: dict, ttl_hours: int = 1):
    """Cache an answer."""
    try:
        import json
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO answer_cache (cache_key, query_text, answer_text, meta, expires_at)
                       VALUES (%s, %s, %s, %s::jsonb, NOW() + INTERVAL '%s hours')
                       ON CONFLICT (cache_key) DO UPDATE SET answer_text=EXCLUDED.answer_text, meta=EXCLUDED.meta, expires_at=EXCLUDED.expires_at""",
                    (cache_key, query, answer, json.dumps(meta, default=str), ttl_hours),
                )
            conn.commit()
    except Exception:
        pass




@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    started_at = time.time()
    request = _apply_channel_defaults(request)

    # Check cache
    cache_key = _cache_key_for_ask(request.query, request.source_types, request.date_from, request.date_to)
    cached = _check_answer_cache(cache_key)
    if cached and not request.debug:
        import json
        answer_text, meta_json = cached
        meta = json.loads(meta_json) if isinstance(meta_json, str) else (meta_json or {})
        meta["cache_hit"] = True
        meta["latency_ms"] = int((time.time() - started_at) * 1000)
        return AskResponse(answer=answer_text, meta=meta)
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
            "channel": request.channel,
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
        "channel": request.channel,
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

    # Save to cache (1h TTL)
    _save_answer_cache(cache_key, request.query, answer, response_meta)

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


# =========================
# Morning Brief endpoint
# =========================

class MorningBriefResponse(BaseModel):
    status: str
    date: str | None = None
    summary_id: int | None = None
    period_start: str | None = None
    period_end: str | None = None
    events_count: int | None = None
    open_loops_count: int | None = None
    entities_count: int | None = None
    summaries_count: int | None = None
    text: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


@app.get("/brief/today", response_model=MorningBriefResponse)
def brief_today(
    force: bool = False,
    days: int = 14,
    date: str | None = None,
) -> MorningBriefResponse:
    """
    Get today's morning brief.
    If not yet generated, generates it on-the-fly.

    Query params:
        force: regenerate even if exists
        days: lookback window (default 7)
        date: override target date (YYYY-MM-DD)
    """
    started_at = time.time()

    result = generate_morning_brief(
        date=date,
        lookback_days=days,
        force=force,
    )

    latency_ms = int((time.time() - started_at) * 1000)

    return MorningBriefResponse(
        status=result.get("status", "unknown"),
        date=result.get("date"),
        summary_id=result.get("summary_id"),
        period_start=result.get("period_start"),
        period_end=result.get("period_end"),
        events_count=result.get("events_count"),
        open_loops_count=result.get("open_loops_count"),
        entities_count=result.get("entities_count"),
        summaries_count=result.get("summaries_count"),
        text=result.get("text"),
        meta={"latency_ms": latency_ms},
    )


# =========================
# Alerts endpoint
# =========================

class AlertItem(BaseModel):
    alert_id: int
    alert_type: str
    severity: str
    title: str
    description: str
    evidence: str | None = None
    is_active: bool = True
    created_at: str | None = None


class AlertsResponse(BaseModel):
    alerts: list[AlertItem]
    meta: dict[str, Any]


@app.get("/alerts", response_model=AlertsResponse)
def alerts(
    active_only: bool = True,
    alert_type: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    refresh: bool = False,
    date: str | None = None,
) -> AlertsResponse:
    """
    Get proactive alerts for Sebastian.

    Query params:
        active_only: only return active alerts (default True)
        alert_type: filter by type (decision_no_followup, conflict_spike,
                    missing_communication, health_clustering)
        severity: filter by severity (high, medium, low)
        limit: max alerts to return (default 50)
        refresh: run detectors before fetching (default False)
        date: reference date for refresh (YYYY-MM-DD, default today)
    """
    started_at = time.time()

    if refresh:
        run_alerts_check(date=date)

    results = get_alerts(
        active_only=active_only,
        alert_type=alert_type,
        severity=severity,
        limit=limit,
    )

    items = [AlertItem(**a) for a in results]
    latency_ms = int((time.time() - started_at) * 1000)

    return AlertsResponse(
        alerts=items,
        meta={
            "count": len(items),
            "active_only": active_only,
            "latency_ms": latency_ms,
        },
    )


# =========================
# Commitment endpoints
# =========================

@app.get("/commitments")
def list_commitments(person: str | None = None, status: str = "open", limit: int = 20):
    """List commitments, optionally filtered by person and status."""
    from app.analysis.commitment_tracker import get_open_commitments, get_commitment_summary
    if person:
        return get_commitment_summary(person_name=person)
    return {"commitments": get_open_commitments(limit=limit)}

@app.post("/commitments/check")
def check_commitments():
    """Run commitment check: overdue detection + fulfillment scan."""
    from app.analysis.commitment_tracker import run_commitment_check
    return run_commitment_check()


# =========================
# Meeting Prep endpoint
# =========================

@app.get("/meeting-prep")
def meeting_prep():
    """Get prep briefs for upcoming meetings."""
    from app.analysis.meeting_prep import run_meeting_prep
    return run_meeting_prep()


# =========================
# Meeting Minutes endpoints
# =========================

@app.get("/meeting-minutes")
def list_minutes(limit: int = 10):
    """List recent meeting minutes."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    SELECT id, document_id, title, meeting_date, participants, summary, created_at
                    FROM meeting_minutes ORDER BY created_at DESC LIMIT %s
                """, (limit,))
                return [{"id": r[0], "document_id": r[1], "title": r[2],
                         "date": str(r[3]) if r[3] else None, "participants": r[4],
                         "summary": r[5], "created": str(r[6])} for r in cur.fetchall()]
            except Exception:
                return []

@app.post("/meeting-minutes/generate")
def generate_minutes():
    """Generate minutes for unprocessed recordings."""
    from app.analysis.meeting_minutes import run_minutes_generation
    return run_minutes_generation()


# =========================
# Sentiment endpoints
# =========================

@app.get("/sentiment/{person_slug}")
def person_sentiment(person_slug: str, weeks: int = 8):
    """Get sentiment trend for a person."""
    from app.analysis.sentiment_tracker import detect_sentiment_trends
    name = person_slug.replace("-", " ").title()
    return detect_sentiment_trends(name, weeks=weeks)

@app.get("/sentiment-alerts")
def sentiment_alerts():
    """Get people with significant sentiment changes."""
    from app.analysis.sentiment_tracker import get_sentiment_alerts
    return {"alerts": get_sentiment_alerts()}


# =========================
# Wellbeing endpoint
# =========================

@app.get("/wellbeing")
def wellbeing(weeks: int = 8):
    """Get Sebastian's wellbeing trend."""
    from app.analysis.wellbeing_monitor import get_wellbeing_trend
    return get_wellbeing_trend(weeks=weeks)

@app.post("/wellbeing/check")
def wellbeing_check():
    """Run wellbeing assessment for current week."""
    from app.analysis.wellbeing_monitor import run_wellbeing_check
    return run_wellbeing_check()


# =========================
# Contract endpoints
# =========================

@app.get("/contracts")
def list_contracts(status: str = "active", limit: int = 20):
    """List tracked contracts."""
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    SELECT id, title, parties, contract_type, value_pln, start_date,
                           end_date, renewal_date, status, created_at
                    FROM contracts WHERE status = %s ORDER BY end_date ASC NULLS LAST LIMIT %s
                """, (status, limit))
                return [{"id": r[0], "title": r[1], "parties": r[2], "type": r[3],
                         "value_pln": float(r[4]) if r[4] else None,
                         "start": str(r[5]) if r[5] else None, "end": str(r[6]) if r[6] else None,
                         "renewal": str(r[7]) if r[7] else None, "status": r[8],
                         "created": str(r[9])} for r in cur.fetchall()]
            except Exception:
                return []

@app.get("/contracts/expiring")
def expiring_contracts(days: int = 30):
    """List contracts expiring within N days."""
    from app.analysis.contract_tracker import check_expiring_contracts
    return {"expiring": check_expiring_contracts(days_ahead=days)}


# =========================
# Delegation endpoint
# =========================

@app.get("/delegation")
def delegation_report():
    """Get delegation effectiveness ranking."""
    from app.analysis.delegation_tracker import run_delegation_report
    return run_delegation_report()

@app.get("/delegation/{person_slug}")
def person_delegation(person_slug: str, months: int = 3):
    """Get delegation score for a person."""
    from app.analysis.delegation_tracker import calculate_delegation_score
    name = person_slug.replace("-", " ").title()
    return calculate_delegation_score(name, months=months)


# =========================
# Blind Spots endpoint
# =========================

@app.get("/blind-spots")
def blind_spots():
    """Detect knowledge gaps in Gilbertus's data."""
    from app.analysis.blind_spot_detector import run_blind_spot_scan
    return run_blind_spot_scan()


# =========================
# Network Graph endpoint
# =========================

@app.get("/network")
def network_graph():
    """Communication network analysis."""
    from app.analysis.network_graph import run_network_analysis
    return run_network_analysis()


# =========================
# Predictive Alerts endpoint
# =========================

@app.get("/predictions")
def predictive_alerts():
    """Get active predictive alerts."""
    from app.analysis.predictive_alerts import run_predictive_scan
    return run_predictive_scan()


# =========================
# Weekly Synthesis endpoint
# =========================

@app.get("/weekly-synthesis")
def weekly_synthesis(date: str | None = None, force: bool = False):
    """Get or generate weekly executive synthesis."""
    from app.retrieval.weekly_synthesis import generate_weekly_synthesis
    return generate_weekly_synthesis(date=date, force=force)


# =========================
# Response Drafter endpoint
# =========================

@app.post("/response-drafter/run")
def run_drafter(minutes: int = 30):
    """Run the smart response drafter."""
    from app.orchestrator.response_drafter import run_response_drafter
    return run_response_drafter(minutes=minutes)


# =========================
# Cron Registry endpoints
# =========================

@app.get("/crons")
def cron_list(user: str | None = None, category: str | None = None):
    """List cron jobs from registry, optionally filtered by user and category."""
    from app.orchestrator.cron_registry import list_jobs
    return {"jobs": list_jobs(username=user, category=category)}

@app.get("/crons/summary")
def cron_summary():
    """Cron registry summary: jobs by category and user."""
    from app.orchestrator.cron_registry import get_registry_summary
    return get_registry_summary()

@app.post("/crons/{job_name}/enable")
def cron_enable(job_name: str, user: str = "sebastian"):
    """Enable a cron job for a user."""
    from app.orchestrator.cron_registry import enable_job
    return enable_job(job_name, user)

@app.post("/crons/{job_name}/disable")
def cron_disable(job_name: str, user: str = "sebastian"):
    """Disable a cron job for a user."""
    from app.orchestrator.cron_registry import disable_job
    return disable_job(job_name, user)

@app.get("/crons/generate/{user}")
def cron_generate(user: str = "sebastian"):
    """Generate crontab file for a user from registry."""
    from app.orchestrator.cron_registry import generate_crontab
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(generate_crontab(user))


# =========================
# Action Outcomes endpoint
# =========================

@app.get("/action-outcomes")
def action_outcomes(days: int = 30):
    """Get action effectiveness summary."""
    from app.analysis.action_outcome_tracker import get_action_effectiveness_summary
    return get_action_effectiveness_summary(days=days)

@app.post("/action-outcomes/check")
def check_outcomes():
    """Run outcome checks on recent actions."""
    from app.analysis.action_outcome_tracker import run_outcome_checks
    return run_outcome_checks()


# =========================
# Decision Intelligence endpoint
# =========================

@app.get("/decision-intelligence")
def decision_intel(months: int = 6):
    """Decision patterns, confidence calibration, bias detection."""
    from app.analysis.decision_intelligence import analyze_decision_patterns
    return analyze_decision_patterns(months=months)

@app.post("/decision-intelligence/run")
def run_decision_intel():
    """Run decision intelligence pipeline."""
    from app.analysis.decision_intelligence import run_decision_intelligence
    return run_decision_intelligence()


# =========================
# Rule Reinforcement endpoint
# =========================

@app.get("/rules/effectiveness")
def rule_effectiveness():
    """Get rule effectiveness report."""
    from app.analysis.rule_reinforcement import get_rule_effectiveness_report
    return get_rule_effectiveness_report()

@app.post("/rules/reinforce")
def reinforce_rules():
    """Run rule reinforcement pipeline."""
    from app.analysis.rule_reinforcement import run_rule_reinforcement
    return run_rule_reinforcement()


# =========================
# Authority Framework endpoint
# =========================

@app.get("/authority")
def authority_levels():
    """List all authority levels."""
    from app.orchestrator.authority import list_authority_levels
    return {"levels": list_authority_levels()}

@app.get("/authority/stats")
def authority_stats(days: int = 90):
    """Get approval pattern analysis and level change suggestions."""
    from app.orchestrator.authority import get_approval_stats
    return get_approval_stats(days=days)

@app.post("/authority/{category}/level/{level}")
def set_authority(category: str, level: int):
    """Set authority level for an action category."""
    from app.orchestrator.authority import update_authority_level
    return update_authority_level(category, level)


# =========================
# Delegation Chain endpoints
# =========================

@app.get("/delegation-chain")
def delegation_dashboard():
    """Delegation tasks dashboard: active, overdue, by assignee."""
    from app.orchestrator.delegation_chain import get_delegation_dashboard
    return get_delegation_dashboard()

@app.post("/delegation-chain/check")
def check_delegations():
    """Check status of all active delegations."""
    from app.orchestrator.delegation_chain import check_delegation_status
    return check_delegation_status()

@app.post("/delegation-chain/delegate")
def delegate(assignee: str, title: str, description: str = "", deadline: str | None = None, priority: str = "medium"):
    """Create a new delegation task."""
    from app.orchestrator.delegation_chain import delegate_task
    return delegate_task(assignee=assignee, title=title, description=description, deadline=deadline, priority=priority)


# =========================
# Response Tracking endpoints
# =========================

@app.get("/response-tracking")
def response_stats(days: int = 30):
    """Response tracking stats: by channel, by person."""
    from app.analysis.response_tracker import get_response_stats
    return get_response_stats(days=days)

@app.post("/response-tracking/run")
def track_responses():
    """Run response tracking scan."""
    from app.analysis.response_tracker import run_response_tracking
    return run_response_tracking()


# =========================
# Communication Effectiveness endpoints
# =========================

@app.get("/channel-effectiveness")
def channel_effectiveness(days: int = 60):
    """Channel effectiveness per person."""
    from app.analysis.channel_effectiveness import run_channel_analysis
    return run_channel_analysis(days=days)

@app.get("/standing-order-effectiveness")
def order_effectiveness(days: int = 30):
    """Standing order effectiveness metrics."""
    from app.analysis.standing_order_effectiveness import run_all_order_analysis
    return run_all_order_analysis(days=days)

@app.get("/authority/suggestions")
def authority_suggestions():
    """Get adaptive authority level change suggestions."""
    from app.orchestrator.adaptive_authority import run_adaptive_authority
    return run_adaptive_authority()


# =========================
# Financial Framework endpoints
# =========================

@app.get("/finance")
def financial_dashboard(company: str | None = None):
    """Financial dashboard: metrics, budgets, alerts, API costs."""
    from app.analysis.financial_framework import get_financial_dashboard
    return get_financial_dashboard(company=company)

@app.post("/finance/metric")
def record_metric(company: str, metric_type: str, value: float, period_start: str, period_end: str, source: str = "manual"):
    """Record a financial metric."""
    from app.analysis.financial_framework import record_metric
    return record_metric(company, metric_type, value, period_start, period_end, source)

@app.post("/finance/budget")
def set_budget(company: str, category: str, planned_amount: float, period_start: str, period_end: str):
    """Set budget for a category."""
    from app.analysis.financial_framework import record_budget
    return record_budget(company, category, planned_amount, period_start, period_end)

@app.post("/finance/estimate-cost")
def estimate_cost(description: str):
    """Estimate cost of a proposed action."""
    from app.analysis.cost_estimator import estimate_cost
    return estimate_cost(description)


# =========================
# Calendar Manager endpoints
# =========================

@app.get("/calendar/events")
def calendar_events(days: int = 7):
    """Get calendar events for next N days."""
    from app.orchestrator.calendar_manager import get_calendar_events
    return {"events": get_calendar_events(days_ahead=days)}

@app.get("/calendar/conflicts")
def calendar_conflicts(days: int = 3):
    """Detect calendar conflicts."""
    from app.orchestrator.calendar_manager import detect_conflicts
    return {"conflicts": detect_conflicts(days_ahead=days)}

@app.get("/calendar/analytics")
def calendar_analytics(days: int = 30):
    """Calendar usage analytics."""
    from app.orchestrator.calendar_manager import get_calendar_analytics
    return get_calendar_analytics(days=days)

@app.get("/calendar/suggestions")
def calendar_suggestions():
    """Suggest meetings based on relationship data."""
    from app.orchestrator.calendar_manager import suggest_meetings
    return {"suggestions": suggest_meetings()}

@app.post("/calendar/block-deep-work")
def block_deep_work(date: str | None = None, start_hour: int = 9, end_hour: int = 11):
    """Block deep work time on calendar."""
    from app.orchestrator.calendar_manager import block_deep_work
    return block_deep_work(date=date, start_hour=start_hour, end_hour=end_hour)


# =========================
# Meeting ROI endpoint
# =========================

@app.get("/meeting-roi")
def meeting_roi():
    """Meeting ROI analysis: which meetings are productive."""
    from app.analysis.meeting_roi import run_meeting_roi_analysis
    return run_meeting_roi_analysis()


# =========================
# Strategic Goals endpoints
# =========================

@app.get("/goals")
def list_goals():
    """List strategic goals with status."""
    from app.analysis.strategic_goals import get_goals_summary
    return get_goals_summary()

@app.get("/goals/{goal_id}")
def get_goal(goal_id: int):
    """Get goal tree with sub-goals, dependencies, progress."""
    from app.analysis.strategic_goals import get_goal_tree
    return get_goal_tree(goal_id=goal_id)

@app.post("/goals")
def create_goal(title: str, target_value: float, unit: str = "PLN", deadline: str | None = None, company: str | None = None, area: str = "business"):
    """Create a strategic goal."""
    from app.analysis.strategic_goals import create_goal
    return create_goal(title=title, target_value=target_value, unit=unit, deadline=deadline, company=company, area=area)

@app.post("/goals/{goal_id}/progress")
def update_progress(goal_id: int, value: float, note: str = ""):
    """Update goal progress."""
    from app.analysis.strategic_goals import update_goal_progress
    return update_goal_progress(goal_id=goal_id, value=value, note=note)


# =========================
# Org Health endpoint
# =========================

@app.get("/org-health")
def org_health(weeks: int = 8):
    """Organizational health score and trend."""
    from app.analysis.org_health import get_health_trend
    return get_health_trend(weeks=weeks)

@app.post("/org-health/assess")
def assess_health():
    """Run health assessment for current week."""
    from app.analysis.org_health import run_health_assessment
    return run_health_assessment()