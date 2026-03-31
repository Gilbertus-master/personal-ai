from pathlib import Path
import os
import random
import time
import logging
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv, dotenv_values
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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
load_dotenv(BASE_DIR / ".env", override=True)

APP_NAME = os.getenv("APP_NAME", "Gilbertus Albans")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
APP_ENV = os.getenv("APP_ENV", "dev")

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)

# --- CORS policy ---
CORS_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS if o.strip()]
if not CORS_ORIGINS:
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8080",
                    "http://127.0.0.1:3000", "http://127.0.0.1:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    max_age=3600,
)

# --- Rate limiting ---
TRUSTED_IPS = {"127.0.0.1", "localhost", "::1"}


def get_rate_limit_key(request: Request) -> str | None:
    """Skip rate limiting for local/internal calls."""
    if request.client and request.client.host in TRUSTED_IPS:
        return None
    return get_remote_address(request)


limiter = Limiter(key_func=get_rate_limit_key)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Feature flag caching ---
_ENV_FLAGS: dict = {}

@app.on_event("startup")
def _load_env_flags():
    """Load feature flags from .env on startup."""
    global _ENV_FLAGS
    _ENV_FLAGS = dotenv_values(BASE_DIR / ".env")


from starlette.middleware.base import BaseHTTPMiddleware
from app.api.auth import api_key_middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=api_key_middleware)

app.include_router(plaud_router)
app.include_router(decisions_router)
app.include_router(insights_router)
app.include_router(presentation_router)
app.include_router(relationships_router)
app.include_router(teams_router)
app.include_router(voice_router)
from app.api.voice_ws import router as voice_ws_router
app.include_router(voice_ws_router)
from app.api.observability import router as observability_router
app.include_router(observability_router)
from app.api.updates import router as updates_router
app.include_router(updates_router)
from app.api.roi import router as roi_router
app.include_router(roi_router)
from app.api.feedback import router as feedback_router
app.include_router(feedback_router)
from app.api.strategic_radar import router as strategic_radar_router
app.include_router(strategic_radar_router)
from app.api.activity import router as activity_router
app.include_router(activity_router)
from app.api.alerts import router as alerts_resolution_router
app.include_router(alerts_resolution_router)
from app.api.alerts_guardian import router as alerts_guardian_router
app.include_router(alerts_guardian_router)
from app.api.errors import router as errors_router
app.include_router(errors_router)


# =========================
# Evaluation endpoint
# =========================

class EvaluateRequest(BaseModel):
    person_slug: str = Field(description="Person slug or 'first-last' name")
    date_from: str | None = Field(default=None, description="YYYY-MM-DD")
    date_to: str | None = Field(default=None, description="YYYY-MM-DD")

@app.post("/evaluate")
@limiter.limit("5/minute")
def evaluate(request: Request, req: EvaluateRequest):
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
@limiter.limit("5/minute")
def scorecard(request: Request, person_slug: str):
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
                       estimated_effort_hours, roi_score, confidence, status, created_at,
                       deadline, action_required_by, urgency
                FROM opportunities WHERE status = %s
                ORDER BY
                  CASE WHEN deadline IS NOT NULL THEN 0 ELSE 1 END,
                  deadline ASC NULLS LAST,
                  roi_score DESC NULLS LAST
                LIMIT %s
            """, (status, limit))
            return [{"id": r[0], "type": r[1], "description": r[2], "value_pln": float(r[3]) if r[3] else 0,
                     "effort_hours": float(r[4]) if r[4] else 0, "roi": float(r[5]) if r[5] else 0,
                     "confidence": r[6], "status": r[7], "created": str(r[8]),
                     "deadline": str(r[9]) if r[9] else None,
                     "action_required_by": str(r[10]) if r[10] else None,
                     "urgency": r[11] or "normal"} for r in cur.fetchall()]

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
@limiter.limit("5/minute")
def correlate(request: Request, req: CorrelationRequest):
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
def health() -> dict[str, str]:
    return {"status": "ok", "service": "gilbertus-api"}


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


@app.get("/code-fixes/manual-queue")
def manual_fix_queue() -> list[dict]:
    """Findings that exhausted auto-fix attempts and need manual review."""
    from app.db.postgres import get_pg_connection
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, file_path, severity, category, title,
                       LEFT(description, 300) as description,
                       fix_attempt_count, fix_attempted_at
                FROM code_review_findings
                WHERE manual_review = TRUE AND resolved = FALSE
                ORDER BY
                    CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 9 END,
                    created_at ASC
            """)
            return [{"id": r[0], "file": r[1], "severity": r[2],
                     "category": r[3], "title": r[4], "description": r[5],
                     "attempts": r[6], "last_attempt": str(r[7])}
                    for r in cur.fetchall()]


@app.get("/admin/roles")
def admin_roles() -> list[dict]:
    """Return all roles with permissions, classifications, modules, and user counts."""
    from app.db.postgres import get_pg_connection

    # Static definitions — mirrors frontend RBAC package
    ROLE_DEFS = [
        {"name": "owner", "level": 100, "label": "Owner", "description": "System owner — full control"},
        {"name": "gilbertus_admin", "level": 99, "label": "System Admin", "description": "Full system administration"},
        {"name": "operator", "level": 70, "label": "Operator", "description": "Infrastructure and sync management"},
        {"name": "ceo", "level": 60, "label": "CEO", "description": "Full business access"},
        {"name": "board", "level": 50, "label": "Board", "description": "Executive-level access"},
        {"name": "director", "level": 40, "label": "Director", "description": "Department-level access"},
        {"name": "manager", "level": 30, "label": "Manager", "description": "Team-level access"},
        {"name": "specialist", "level": 20, "label": "Specialist", "description": "Individual contributor access"},
    ]

    ROLE_PERMS = {
        "owner": ["*"],
        "gilbertus_admin": ["*"],
        "operator": ["config:write:system", "sync:manage", "sync:credentials", "infra:manage", "dev:execute", "commands:task"],
        "ceo": ["data:read:all", "financials:read", "evaluations:read:all", "communications:read:all",
                "config:write:system", "users:manage:all", "queries:create", "prompts:manage",
                "rbac:manage", "commands:email", "commands:ticket", "commands:meeting",
                "commands:task", "commands:sync", "views:configure:own"],
        "board": ["data:read:all", "financials:read", "evaluations:read:reports", "config:write:system",
                  "users:manage:below", "queries:create", "commands:email", "commands:ticket",
                  "commands:meeting", "commands:task", "commands:sync", "views:configure:own"],
        "director": ["data:read:department", "evaluations:read:reports", "communications:read:department",
                     "config:write:department", "queries:create", "commands:email", "commands:ticket",
                     "commands:meeting", "commands:task", "commands:sync", "views:configure:own"],
        "manager": ["data:read:team", "config:write:own", "queries:create:department",
                    "commands:ticket", "commands:meeting", "commands:task", "views:configure:own"],
        "specialist": ["data:read:own", "config:write:own", "commands:task", "views:configure:own"],
    }

    ROLE_CLASSIFICATIONS = {
        "owner": ["public", "internal", "confidential", "ceo_only", "personal"],
        "gilbertus_admin": ["public", "internal", "confidential", "ceo_only", "personal"],
        "ceo": ["public", "internal", "confidential", "ceo_only", "personal"],
        "board": ["public", "internal", "confidential", "personal"],
        "director": ["public", "internal", "personal"],
        "manager": ["public", "internal", "personal"],
        "specialist": ["public", "personal"],
        "operator": [],
    }

    ROLE_MODULES = {
        "owner": ["all"],
        "gilbertus_admin": ["dashboard", "chat", "settings", "admin", "autofixers"],
        "operator": ["dashboard", "chat", "settings", "admin", "autofixers"],
        "ceo": ["dashboard", "brief", "chat", "people", "intelligence", "compliance", "market",
                "finance", "process", "decisions", "calendar", "documents", "voice", "settings"],
        "board": ["dashboard", "brief", "chat", "people", "intelligence", "compliance", "market",
                  "finance", "process", "calendar", "documents", "voice", "settings"],
        "director": ["dashboard", "chat", "people", "compliance", "market", "process",
                     "calendar", "documents", "settings"],
        "manager": ["dashboard", "chat", "calendar", "settings"],
        "specialist": ["dashboard", "chat", "settings"],
    }

    # Get user counts from DB (if omnius tables exist)
    user_counts: dict[str, int] = {}
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT r.name, COUNT(u.id)
                    FROM omnius_roles r
                    LEFT JOIN omnius_users u ON u.role_id = r.id AND u.is_active = TRUE
                    GROUP BY r.name
                """)
                user_counts = {row[0]: row[1] for row in cur.fetchall()}
    except Exception:
        pass

    result = []
    for rd in ROLE_DEFS:
        name = rd["name"]
        result.append({
            **rd,
            "permissions": ROLE_PERMS.get(name, []),
            "classifications": ROLE_CLASSIFICATIONS.get(name, []),
            "modules": ROLE_MODULES.get(name, []),
            "user_count": user_counts.get(name, 0),
        })

    return result


@app.get("/autofixers/dashboard")
def autofixer_dashboard() -> dict:
    """Unified dashboard for both repair pipelines."""
    import json
    from pathlib import Path
    from app.db.postgres import get_pg_connection

    result: dict = {}

    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            # ── Code fixer overview ──
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as resolved,
                    SUM(CASE WHEN NOT resolved THEN 1 ELSE 0 END) as open,
                    SUM(CASE WHEN NOT resolved AND fix_attempt_count >= 2 THEN 1 ELSE 0 END) as stuck,
                    SUM(CASE WHEN manual_review THEN 1 ELSE 0 END) as manual_review
                FROM code_review_findings
            """)
            row = cur.fetchone()
            total = row[0] or 0
            resolved = row[1] or 0
            code_fixer = {
                "total": total,
                "resolved": resolved,
                "open": row[2] or 0,
                "stuck": row[3] or 0,
                "manual_review": row[4] or 0,
                "by_severity": {},
                "by_category": {},
                "by_tier": {},
                "success_rate": round(resolved / total * 100, 1) if total else 0,
                "last_fix": None,
            }

            # By severity (open only)
            cur.execute("""
                SELECT severity, COUNT(*)
                FROM code_review_findings WHERE NOT resolved
                GROUP BY severity
            """)
            code_fixer["by_severity"] = {r[0]: r[1] for r in cur.fetchall()}

            # By category (open only)
            cur.execute("""
                SELECT category, COUNT(*)
                FROM code_review_findings WHERE NOT resolved
                GROUP BY category
            """)
            code_fixer["by_category"] = {r[0]: r[1] for r in cur.fetchall()}

            # By tier
            cur.execute("""
                SELECT COALESCE(tier, 1), COUNT(*)
                FROM code_review_findings WHERE NOT resolved
                GROUP BY COALESCE(tier, 1)
            """)
            code_fixer["by_tier"] = {f"tier{r[0]}": r[1] for r in cur.fetchall()}

            # Last fix
            cur.execute("""
                SELECT MAX(resolved_at) FROM code_review_findings WHERE resolved
            """)
            last = cur.fetchone()
            if last and last[0]:
                code_fixer["last_fix"] = str(last[0])

            result["code_fixer"] = code_fixer

            # ── Webapp fixer ──
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as resolved,
                    SUM(CASE WHEN NOT resolved THEN 1 ELSE 0 END) as open
                FROM app_errors
            """)
            wrow = cur.fetchone()
            webapp = {
                "total_errors": wrow[0] or 0,
                "resolved": wrow[1] or 0,
                "open": wrow[2] or 0,
                "server_status": "unknown",
                "consecutive_failures": 0,
                "last_check": None,
                "routes_monitored": 0,
            }
            # Read state file if exists
            state_path = Path("logs/webapp_autofix_state.json")
            if state_path.exists():
                try:
                    state = json.loads(state_path.read_text())
                    webapp["server_status"] = state.get("server_status", "unknown")
                    webapp["consecutive_failures"] = state.get("consecutive_failures", 0)
                    webapp["last_check"] = state.get("last_check")
                    webapp["routes_monitored"] = state.get("routes_monitored", 0)
                except Exception:
                    pass
            result["webapp_fixer"] = webapp

            # ── Daily history (14 days) ──
            cur.execute("""
                SELECT DATE(created_at) as day,
                    COUNT(*) as found,
                    SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as fixed
                FROM code_review_findings
                WHERE created_at > NOW() - INTERVAL '14 days'
                GROUP BY DATE(created_at) ORDER BY day
            """)
            code_days = {str(r[0]): {"found": r[1], "fixed": r[2]} for r in cur.fetchall()}

            cur.execute("""
                SELECT DATE(created_at) as day,
                    COUNT(*) as total,
                    SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as fixed
                FROM app_errors
                WHERE created_at > NOW() - INTERVAL '14 days'
                GROUP BY DATE(created_at) ORDER BY day
            """)
            webapp_days = {str(r[0]): {"errors": r[1], "fixed": r[2]} for r in cur.fetchall()}

            all_days = sorted(set(list(code_days.keys()) + list(webapp_days.keys())))
            result["daily_history"] = [
                {
                    "date": d,
                    "found": code_days.get(d, {}).get("found", 0),
                    "fixed": code_days.get(d, {}).get("fixed", 0),
                    "webapp_errors": webapp_days.get(d, {}).get("errors", 0),
                    "webapp_fixed": webapp_days.get(d, {}).get("fixed", 0),
                }
                for d in all_days
            ]

            # ── Manual queue ──
            cur.execute("""
                SELECT id, file_path, severity, category, title,
                    LEFT(description, 500) as description,
                    fix_attempt_count, tier3_attempted, tier3_last_error,
                    created_at, LEFT(suggested_fix, 500) as suggested_fix
                FROM code_review_findings
                WHERE NOT resolved AND (manual_review OR fix_attempt_count >= 3)
                ORDER BY
                    CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 9 END,
                    created_at
            """)
            result["manual_queue"] = [
                {
                    "id": r[0], "file_path": r[1], "severity": r[2],
                    "category": r[3], "title": r[4], "description": r[5],
                    "attempts": r[6] or 0, "tier3_attempted": bool(r[7]),
                    "tier3_last_error": r[8], "created_at": str(r[9]),
                    "suggested_fix": r[10],
                }
                for r in cur.fetchall()
            ]

    return result


@app.get("/conversation/windows")
def list_conversation_windows() -> list[dict]:
    """Active conversation windows (last 24h)."""
    from app.db.postgres import get_pg_connection
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT channel_key, message_count, total_chars,
                       last_active, created_at
                FROM conversation_windows
                WHERE last_active > NOW() - INTERVAL '24 hours'
                ORDER BY last_active DESC
            """)
            return [{"channel": r[0], "messages": r[1], "chars": r[2],
                     "last_active": str(r[3]), "created": str(r[4])}
                    for r in cur.fetchall()]


@app.get("/status")
@limiter.limit("10/minute")
def system_status(request: Request) -> dict[str, Any]:
    """
    System status dashboard — protected by API key when GILBERTUS_API_KEY is set.
    Returns DB stats, embedding status, source breakdown,
    last backup, service health, and cron jobs.
    """
    api_key = os.getenv("GILBERTUS_API_KEY", "")
    if api_key:
        provided = request.headers.get("X-API-Key", "")
        client_ip = request.client.host if request.client else ""
        if client_ip not in {"127.0.0.1", "localhost", "::1"} and provided != api_key:
            raise HTTPException(status_code=401, detail="X-API-Key required for /status")
    started_at = time.time()
    result: dict[str, Any] = {}

    # ── 1. Database stats ──────────────────────────────────────────────
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM documents")
                document_count = cur.fetchall()[0][0]

                cur.execute("SELECT count(*) FROM chunks")
                chunk_count = cur.fetchall()[0][0]

                cur.execute("SELECT count(*) FROM entities")
                entity_count = cur.fetchall()[0][0]

                cur.execute("SELECT count(*) FROM events")
                event_count = cur.fetchall()[0][0]

                cur.execute("SELECT count(*) FROM summaries")
                summary_count = cur.fetchall()[0][0]

                # insights table may not exist yet
                try:
                    cur.execute("SELECT count(*) FROM insights")
                    insight_count = cur.fetchall()[0][0]
                except Exception:
                    conn.rollback()
                    insight_count = None

                try:
                    cur.execute("SELECT count(*) FROM alerts")
                    alert_count = cur.fetchall()[0][0]
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
                total = cur.fetchall()[0][0]

                cur.execute(
                    "SELECT count(*) FROM chunks WHERE embedding_id IS NOT NULL"
                )
                done = cur.fetchall()[0][0]

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

def _get_latest_cost_for_module(module: str) -> dict:
    """Get most recent api_costs entry for a module (written moments ago)."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT model, input_tokens, output_tokens, cost_usd
                       FROM api_costs
                       WHERE module = %s
                       ORDER BY created_at DESC LIMIT 1""",
                    (module,),
                )
                row = cur.fetchone()
        if row:
            return {"model": row[0], "input_tokens": row[1],
                    "output_tokens": row[2], "cost_usd": float(row[3] or 0)}
    except Exception:
        pass
    return {}


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


def _save_answer_cache(cache_key: str, query: str, answer: str, meta: dict, ttl_hours: float = 0.5):
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
@limiter.limit("30/minute")
def ask(body: AskRequest, request: Request) -> AskResponse:
    started_at = time.time()
    from app.db.stage_timer import StageTimer
    timer = StageTimer()
    caller_ip = request.client.host if request.client else None
    channel_key = f"{body.channel or 'api'}:{body.session_id or 'anonymous'}"
    ask_req = _apply_channel_defaults(body)

    # Prompt injection detection
    from app.utils.input_sanitizer import sanitize_query
    sanitized = sanitize_query(ask_req.query)
    if sanitized.suspicious:
        import structlog
        structlog.get_logger("security").warning(
            "prompt_injection_detected",
            flags=sanitized.flags,
            channel=ask_req.channel,
            query_preview=ask_req.query[:100],
        )
    ask_req = ask_req.model_copy(update={"query": sanitized.text})


    # Conversation history (sliding window)
    from app.db.conversation_store import get_store
    conversation_context = ""
    conv_store = None
    previous_answer_summary = ""
    if ask_req.channel or ask_req.session_id:
        conv_store = get_store(ask_req.channel, ask_req.session_id)
        conversation_context = conv_store.as_context_string()
        previous_answer_summary = conv_store.get_last_answer_summary()

    # Check cache
    cache_key = _cache_key_for_ask(ask_req.query, ask_req.source_types, ask_req.date_from, ask_req.date_to)
    cached = _check_answer_cache(cache_key)
    if cached and not ask_req.debug:
        import json
        answer_text, meta_json = cached
        meta = json.loads(meta_json) if isinstance(meta_json, str) else (meta_json or {})
        meta["cache_hit"] = True
        meta["latency_ms"] = int((time.time() - started_at) * 1000)
        return AskResponse(answer=answer_text, meta=meta)
    request_payload = model_to_dict(ask_req)

    timer.start("interpret")
    interpreted = interpret_query(
        query=ask_req.query,
        source_types=ask_req.source_types,
        source_names=ask_req.source_names,
        date_from=ask_req.date_from,
        date_to=ask_req.date_to,
        mode=ask_req.mode,
        previous_answer_summary=previous_answer_summary,
    )

    prefetch_k = get_prefetch_k(
        interpreted.question_type,
        interpreted.analysis_depth,
    )

    answer_match_limit = get_answer_match_limit(
        interpreted.question_type,
        interpreted.analysis_depth,
    )

    final_match_limit = max(ask_req.top_k, min(answer_match_limit, ask_req.top_k * 3))
    timer.end("interpret")

    # Orchestrator-Workers: decompose complex queries into sub-questions
    if (interpreted.sub_questions
            and _ENV_FLAGS.get("ENABLE_ORCHESTRATOR", "false").lower() == "true"):
        timer.start("orchestrator")
        from app.retrieval.orchestrator import decompose_and_synthesize
        answer = decompose_and_synthesize(
            query=ask_req.query,
            sub_questions=interpreted.sub_questions,
            source_types=interpreted.source_types,
            source_names=interpreted.source_names,
            date_from=interpreted.date_from,
            date_to=interpreted.date_to,
            question_type=interpreted.question_type,
            analysis_depth=interpreted.analysis_depth,
            answer_length=ask_req.answer_length,
            conversation_context=conversation_context,
        )
        timer.end("orchestrator")

        # Save to conversation window
        if conv_store:
            conv_store.add("user", ask_req.query)
            conv_store.add("assistant", answer)

        latency_ms = int((time.time() - started_at) * 1000)
        response_meta = {
            "question_type": interpreted.question_type,
            "analysis_depth": interpreted.analysis_depth,
            "orchestrator": True,
            "sub_questions": len(interpreted.sub_questions),
            "normalized_query": interpreted.normalized_query,
            "channel": ask_req.channel,
        }
        run_id = persist_ask_run_best_effort(
            session_id=None,
            request_payload=model_to_dict(ask_req),
            response_payload={"answer": answer, "meta": response_meta},
            interpretation={
                "normalized_query": interpreted.normalized_query,
                "question_type": interpreted.question_type,
                "analysis_depth": interpreted.analysis_depth,
                "sub_questions": interpreted.sub_questions,
            },
            matches=[],
            latency_ms=latency_ms,
            stage_ms=timer.to_dict(),
            cache_hit=False,
            caller_ip=caller_ip,
            channel_key=channel_key,
        )
        # Persist per-stage timing (orchestrator path)
        try:
            from app.db.timing_persistence import save_timing
            _stage = timer.to_dict()
            save_timing(
                question_type=interpreted.question_type,
                analysis_depth=interpreted.analysis_depth,
                total_ms=latency_ms,
                interpret_ms=_stage.get("interpret"),
                channel=ask_req.channel,
            )
        except Exception:
            pass

        return AskResponse(answer=answer, meta=response_meta, run_id=run_id)

    # Tool routing: smart source group inference when source_types not explicit
    if _ENV_FLAGS.get("ENABLE_TOOL_ROUTING", "false").lower() == "true":
        from app.retrieval.tool_router import route_tools
        routed_sources = route_tools(
            query=ask_req.query,
            question_type=interpreted.question_type,
            source_types=interpreted.source_types,
        )
        if routed_sources and not interpreted.source_types:
            interpreted = interpreted.model_copy(update={"source_types": routed_sources})

    timer.start("retrieve")
    # Deep routing: specialized retrieval per question_type
    _enable_routing = _ENV_FLAGS.get("ENABLE_DEEP_ROUTING", "false").lower() == "true"
    _enable_parallel = _ENV_FLAGS.get("ENABLE_PARALLEL_RETRIEVAL", "false").lower() == "true"
    if _enable_routing:
        from app.retrieval.query_router import route_retrieval
        matches = route_retrieval(
            interpreted,
            top_k=answer_match_limit,
            prefetch_k=prefetch_k,
            enable_parallel=_enable_parallel,
        )
    else:
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
            query=ask_req.query,
            top_k=answer_match_limit,
            source_types=ask_req.source_types,
            source_names=ask_req.source_names,
            date_from=ask_req.date_from,
            date_to=ask_req.date_to,
            prefetch_k=prefetch_k,
            question_type=interpreted.question_type,
        )
    timer.end("retrieve")

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
            "answer_style": ask_req.answer_style,
            "answer_length": ask_req.answer_length,
            "allow_quotes": ask_req.allow_quotes,
            "channel": ask_req.channel,
            "debug": ask_req.debug,
        }

        response_payload = {
            "answer": "Nie znalazłem wystarczająco trafnego kontekstu dla tego pytania.",
            "sources": [] if ask_req.debug else None,
            "matches": [] if ask_req.debug else None,
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
            stage_ms=timer.to_dict(),
            cache_hit=False,
            caller_ip=caller_ip,
            channel_key=channel_key,
        )

        # Persist per-stage timing (no-matches fallback path)
        try:
            from app.db.timing_persistence import save_timing
            _stage = timer.to_dict()
            save_timing(
                question_type=interpreted.question_type,
                analysis_depth=interpreted.analysis_depth,
                used_fallback=used_fallback,
                retrieved_count=0,
                total_ms=latency_ms,
                interpret_ms=_stage.get("interpret"),
                retrieve_ms=_stage.get("retrieve"),
                channel=ask_req.channel,
            )
        except Exception:
            pass

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

    # Context size guard — trim to top-N if context too large
    MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "80000"))
    total_context_chars = sum(len(m.get("text", "")) for m in redacted_matches_for_answer)
    if total_context_chars > MAX_CONTEXT_CHARS:
        import structlog as _sl
        _ctx_log = _sl.get_logger("circuit_breaker")
        original_count = len(redacted_matches_for_answer)
        trimmed = sorted(redacted_matches_for_answer, key=lambda m: m.get("score", 0), reverse=True)
        cumulative = 0
        cut_idx = len(trimmed)
        for i, m in enumerate(trimmed):
            cumulative += len(m.get("text", ""))
            if cumulative > MAX_CONTEXT_CHARS:
                cut_idx = i
                break
        redacted_matches_for_answer = trimmed[:max(cut_idx, 1)]
        _ctx_log.warning("context_trimmed", original_chars=total_context_chars,
                         original_matches=original_count,
                         trimmed_to=len(redacted_matches_for_answer))

    timer.start("answer")
    answer = answer_question(
        query=ask_req.query,
        matches=redacted_matches_for_answer,
        question_type=interpreted.question_type,
        analysis_depth=interpreted.analysis_depth,
        include_sources=ask_req.include_sources,
        answer_style=ask_req.answer_style,
        answer_length=ask_req.answer_length,
        allow_quotes=ask_req.allow_quotes,
        conversation_context=conversation_context,
    )
    timer.end("answer")

    # Answer self-evaluation gate (Evaluator-Optimizer pattern) — sampled
    EVAL_SAMPLE_RATE = float(os.getenv("ANSWER_EVAL_SAMPLE_RATE", "0.1"))
    MAX_EVAL_RETRIES = int(os.getenv("MAX_EVAL_RETRIES", "2"))
    eval_result = None
    if (_ENV_FLAGS.get("ENABLE_ANSWER_EVAL", "false").lower() == "true"
            and EVAL_SAMPLE_RATE > 0
            and random.random() < EVAL_SAMPLE_RATE):
        try:
            timer.start("evaluate")
            from app.retrieval.answer_evaluator import evaluate_answer
            eval_retries = 0
            eval_result = evaluate_answer(
                query=ask_req.query,
                answer=answer,
                question_type=interpreted.question_type,
            )
            while (eval_result and eval_result.should_retry and eval_result.feedback
                   and eval_retries < MAX_EVAL_RETRIES):
                eval_retries += 1
                answer = answer_question(
                    query=f"{ask_req.query}\n\n[FEEDBACK EWALUATORA: {eval_result.feedback}]",
                    matches=redacted_matches_for_answer,
                    question_type=interpreted.question_type,
                    analysis_depth=interpreted.analysis_depth,
                    include_sources=ask_req.include_sources,
                    answer_style=ask_req.answer_style,
                    answer_length=ask_req.answer_length,
                    allow_quotes=ask_req.allow_quotes,
                    conversation_context=conversation_context,
                )
                eval_result = evaluate_answer(
                    query=ask_req.query,
                    answer=answer,
                    question_type=interpreted.question_type,
                )
            # Log low-quality answers
            if eval_result and eval_result.avg_score < 0.6:
                import structlog
                structlog.get_logger("quality").warning(
                    "low_quality_answer",
                    score=eval_result.avg_score,
                    feedback=eval_result.feedback,
                    query=ask_req.query[:100],
                )
            # Persist evaluation for trend analysis
            if eval_result:
                try:
                    from app.analysis.feedback_persistence import save_answer_evaluation as _save_eval
                    _save_eval(
                        ask_run_id=None,  # will be set after persist_ask_run
                        relevance=eval_result.relevance,
                        grounding=eval_result.grounding,
                        depth=eval_result.depth,
                        overall=eval_result.avg_score,
                        feedback=eval_result.feedback,
                    )
                except Exception:
                    pass  # feedback persistence is non-critical
            timer.end("evaluate")
        except Exception:
            pass  # evaluator jest opcjonalny — nie blokuj głównego flow

    # Save to conversation window
    if conv_store:
        conv_store.add("user", ask_req.query)
        conv_store.add("assistant", answer)

    response_sources = build_sources_from_matches(redacted_matches_for_answer) if ask_req.debug else None
    response_matches = build_debug_matches(redacted_matches_for_answer) if ask_req.debug else None

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
        "answer_style": ask_req.answer_style,
        "answer_length": ask_req.answer_length,
        "allow_quotes": ask_req.allow_quotes,
        "channel": ask_req.channel,
        "debug": ask_req.debug,
        "eval_score": eval_result.avg_score if eval_result else None,
        "eval_retried": eval_result.should_retry if eval_result else None,
    }

    latency_ms = int((time.time() - started_at) * 1000)
    stage_breakdown = timer.to_dict()

    run_cost_data = _get_latest_cost_for_module("retrieval.answering")

    error_flag = (
        answer.startswith("Wystąpił błąd")
        or answer.startswith("ERROR")
        or answer.startswith("Nie udało")
        or latency_ms > 90_000
    )

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
        stage_ms=stage_breakdown,
        model_used=run_cost_data.get("model"),
        input_tokens=run_cost_data.get("input_tokens", 0),
        output_tokens=run_cost_data.get("output_tokens", 0),
        cost_usd=run_cost_data.get("cost_usd"),
        error_flag=error_flag,
        error_message=answer[:200] if error_flag else None,
        cache_hit=bool(cached),
        caller_ip=caller_ip,
        channel_key=channel_key,
    )

    # Persist per-stage timing
    try:
        from app.db.timing_persistence import save_timing
        save_timing(
            question_type=interpreted.question_type,
            analysis_depth=interpreted.analysis_depth,
            used_fallback=used_fallback,
            retrieved_count=len(redacted_matches_for_answer),
            total_ms=latency_ms,
            interpret_ms=stage_breakdown.get("interpret"),
            retrieve_ms=stage_breakdown.get("retrieve"),
            answer_ms=stage_breakdown.get("answer"),
            channel=ask_req.channel,
            model_used=run_cost_data.get("model"),
        )
    except Exception:
        pass  # timing is non-critical

    # Save to cache (30min TTL)
    _save_answer_cache(cache_key, ask_req.query, answer, response_meta, ttl_hours=0.5)

    ask_response = AskResponse(
        answer=answer,
        sources=response_sources,
        matches=response_matches,
        meta=response_meta,
        run_id=run_id,
    )
    from fastapi.responses import JSONResponse
    json_resp = JSONResponse(content=ask_response.model_dump())
    if run_id:
        json_resp.headers["X-Gilbertus-Run-ID"] = str(run_id)
    return json_resp


# =========================
# Performance stats endpoint
# =========================

@app.get("/performance/stats")
def performance_stats(days: int = 7):
    """Per-stage timing statistics for the last N days."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        question_type,
                        COUNT(*) as request_count,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_ms)) as p50_total,
                        ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_ms)) as p95_total,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY interpret_ms)) as p50_interpret,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY retrieve_ms)) as p50_retrieve,
                        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY answer_ms)) as p50_answer,
                        ROUND(AVG(retrieved_count::numeric), 1) as avg_chunks,
                        ROUND((AVG(CASE WHEN used_fallback THEN 1.0 ELSE 0.0 END) * 100)::numeric, 1) as fallback_pct
                    FROM query_stage_times
                    WHERE created_at > NOW() - (%(days)s || ' days')::interval
                    GROUP BY question_type
                    ORDER BY request_count DESC
                """, {"days": days})
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return {"days": days, "by_question_type": rows}
    except Exception as e:
        return {"error": str(e)}


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
@limiter.limit("30/minute")
def summary_generate(request: Request, body: SummaryGenerateRequest) -> SummaryGenerateResponse:
    started_at = time.time()

    if body.summary_type == "weekly":
        results = generate_weekly_summaries(body.date, areas=body.areas)
    else:
        results = generate_daily_summaries(body.date, areas=body.areas)

    items = [SummaryItem(**r) for r in results]
    latency_ms = int((time.time() - started_at) * 1000)

    return SummaryGenerateResponse(
        results=items,
        meta={
            "summary_type": body.summary_type,
            "date": body.date,
            "areas": body.areas or AREAS,
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
@limiter.limit("30/minute")
def brief_today(
    request: Request,
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
# Compliance endpoints
# =========================

@app.get("/compliance/dashboard")
def compliance_dashboard():
    """Overall compliance status dashboard."""
    from app.analysis.legal_compliance import get_compliance_dashboard
    return get_compliance_dashboard()

@app.get("/compliance/areas")
def compliance_areas():
    """List all compliance areas."""
    from app.analysis.legal_compliance import list_areas
    return {"areas": list_areas()}

@app.get("/compliance/areas/{code}")
def compliance_area_detail(code: str):
    """Detail for specific compliance area."""
    from app.analysis.legal_compliance import get_area_detail
    return get_area_detail(code.upper())

@app.get("/compliance/matters")
def compliance_matters(status: str | None = None, area_code: str | None = None, priority: str | None = None, limit: int = 20):
    """List compliance matters with filters."""
    from app.analysis.legal_compliance import list_matters
    return {"matters": list_matters(status=status, area_code=area_code, priority=priority, limit=limit)}

@app.post("/compliance/matters")
def create_compliance_matter(body: dict):
    """Create new compliance matter."""
    from app.analysis.legal_compliance import create_matter
    return create_matter(
        title=body.get("title", ""),
        matter_type=body.get("matter_type", "other"),
        area_code=body.get("area_code"),
        description=body.get("description"),
        priority=body.get("priority", "medium"),
        contract_id=body.get("contract_id"),
        source_regulation=body.get("source_regulation"),
    )

@app.get("/compliance/matters/{matter_id}")
def compliance_matter_detail(matter_id: int):
    """Full detail for compliance matter."""
    from app.analysis.legal_compliance import get_matter_detail
    return get_matter_detail(matter_id)


@app.get("/compliance/obligations")
def compliance_obligations(area_code: str | None = None, status: str | None = None, limit: int = 50):
    """List compliance obligations."""
    from app.analysis.legal_compliance import list_obligations
    return {"obligations": list_obligations(area_code=area_code, compliance_status=status, limit=limit)}


@app.get("/compliance/obligations/overdue")
def compliance_obligations_overdue():
    """List overdue obligations."""
    from app.analysis.legal_compliance import get_overdue_obligations
    return {"overdue": get_overdue_obligations()}


@app.post("/compliance/obligations")
def create_compliance_obligation(body: dict):
    """Create new compliance obligation."""
    from app.analysis.legal_compliance import create_obligation
    return create_obligation(**{k: v for k, v in body.items() if v is not None})


@app.post("/compliance/obligations/{obligation_id}/fulfill")
def fulfill_compliance_obligation(obligation_id: int, body: dict = {}):
    """Mark obligation as fulfilled."""
    from app.analysis.legal_compliance import fulfill_obligation
    return fulfill_obligation(obligation_id, body.get("evidence_description"))


@app.get("/compliance/deadlines")
def compliance_deadlines(days_ahead: int = 30, area_code: str | None = None):
    """Upcoming compliance deadlines."""
    from app.db.postgres import get_pg_connection
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT d.id, d.title, d.deadline_date, d.deadline_type, d.status,
                       d.recurrence, a.code as area_code, a.name_pl as area_name
                FROM compliance_deadlines d
                LEFT JOIN compliance_areas a ON a.id = d.area_id
                WHERE d.deadline_date <= CURRENT_DATE + %s
                  AND d.status IN ('pending','in_progress')
            """
            params: list = [days_ahead]
            if area_code:
                sql += " AND a.code = %s"
                params.append(area_code.upper())
            sql += " ORDER BY d.deadline_date ASC"
            cur.execute(sql, params)
            return {"deadlines": [
                {"id": r[0], "title": r[1], "date": str(r[2]), "type": r[3],
                 "status": r[4], "recurrence": r[5], "area_code": r[6], "area_name": r[7]}
                for r in cur.fetchall()
            ]}


@app.get("/compliance/deadlines/overdue")
def compliance_deadlines_overdue():
    """Overdue compliance deadlines."""
    from app.db.postgres import get_pg_connection
    with get_pg_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.deadline_date, d.deadline_type,
                       a.code, a.name_pl,
                       CURRENT_DATE - d.deadline_date as days_overdue
                FROM compliance_deadlines d
                LEFT JOIN compliance_areas a ON a.id = d.area_id
                WHERE d.status = 'overdue'
                   OR (d.deadline_date < CURRENT_DATE AND d.status = 'pending')
                ORDER BY d.deadline_date ASC
            """)
            return {"overdue": [
                {"id": r[0], "title": r[1], "date": str(r[2]), "type": r[3],
                 "area_code": r[4], "area_name": r[5], "days_overdue": r[6]}
                for r in cur.fetchall()
            ]}


@app.post("/compliance/matters/{matter_id}/research")
def compliance_research(matter_id: int, body: dict = {}):
    """Trigger AI research on compliance matter."""
    from app.analysis.legal_compliance import research_regulation
    return research_regulation(matter_id, query=body.get("query"))


@app.post("/compliance/matters/{matter_id}/advance")
def compliance_advance(matter_id: int, body: dict = {}):
    """Advance matter to next phase."""
    from app.analysis.legal_compliance import advance_matter_phase
    return advance_matter_phase(matter_id, force_phase=body.get("force_phase"))


@app.post("/compliance/matters/{matter_id}/report")
def compliance_report(matter_id: int):
    """Generate compliance report for matter."""
    from app.analysis.legal_compliance import generate_compliance_report
    return generate_compliance_report(matter_id)


@app.get("/compliance/risks")
def compliance_risks(area_code: str | None = None, status: str = "open", limit: int = 50):
    """List risk assessments."""
    from app.analysis.legal.risk_assessor import list_risks
    return {"risks": list_risks(area_code=area_code, status=status, limit=limit)}


@app.get("/compliance/risks/heatmap")
def compliance_risk_heatmap():
    """Risk heatmap data."""
    from app.analysis.legal.risk_assessor import get_risk_heatmap
    return get_risk_heatmap()


@app.post("/compliance/scan")
def compliance_scan(hours: int = 24):
    """Scan recent chunks for regulatory changes."""
    from app.analysis.legal.regulatory_scanner import scan_for_regulatory_changes
    return scan_for_regulatory_changes(hours=hours)


@app.get("/compliance/documents")
def compliance_documents(area_code: str | None = None, doc_type: str | None = None,
                         status: str | None = None, limit: int = 50):
    """List compliance documents with filters."""
    from app.analysis.legal_compliance import list_documents
    return {"documents": list_documents(area_code=area_code, doc_type=doc_type,
                                        status=status, limit=limit)}


@app.get("/compliance/documents/stale")
def compliance_stale_documents(days: int = 0):
    """Get documents overdue for review."""
    from app.analysis.legal_compliance import get_stale_documents
    return {"stale_documents": get_stale_documents(days)}


@app.post("/compliance/documents/generate")
def compliance_generate_document(body: dict):
    """Generate a compliance document using AI."""
    from app.analysis.legal_compliance import generate_document
    return generate_document(
        matter_id=body["matter_id"], doc_type=body["doc_type"],
        title=body.get("title"), template_hint=body.get("template_hint"),
        signers=body.get("signers"), valid_months=body.get("valid_months", 12))


@app.post("/compliance/documents/{doc_id}/approve")
def compliance_approve_document(doc_id: int, body: dict = {}):
    """Approve a compliance document."""
    from app.analysis.legal.document_generator import approve_document
    return approve_document(doc_id, body.get("approved_by", "sebastian"))


@app.post("/compliance/documents/{doc_id}/sign")
def compliance_sign_document(doc_id: int, body: dict):
    """Register electronic signature on a document."""
    from app.analysis.legal.document_generator import sign_document
    return sign_document(doc_id, body["signer_name"])


# --- Training endpoints ---

@app.get("/compliance/trainings")
def compliance_trainings(status: str | None = None, area_code: str | None = None, limit: int = 20):
    """List compliance trainings with filters."""
    from app.analysis.legal_compliance import list_trainings
    return {"trainings": list_trainings(status=status, area_code=area_code, limit=limit)}


@app.get("/compliance/trainings/{training_id}/status")
def compliance_training_status(training_id: int):
    """Get training status with per-person breakdown."""
    from app.analysis.legal_compliance import get_training_status
    return get_training_status(training_id)


@app.post("/compliance/trainings")
def create_compliance_training(body: dict):
    """Create a new compliance training."""
    from app.analysis.legal_compliance import create_training
    return create_training(**{k: v for k, v in body.items() if v is not None})


@app.post("/compliance/trainings/{training_id}/complete")
def complete_compliance_training(training_id: int, body: dict):
    """Mark training as completed for a person."""
    from app.analysis.legal.training_manager import complete_training
    return complete_training(training_id, body["person_id"], body.get("score"))


# --- Communication & Reporting endpoints ---

@app.get("/compliance/report/daily")
def compliance_daily_report():
    """Generate daily compliance status update."""
    from app.analysis.legal.compliance_reporter import generate_daily_update
    update = generate_daily_update()
    return {"report": update or "No compliance issues to report"}

@app.get("/compliance/report/weekly")
def compliance_weekly_report():
    """Generate weekly compliance report."""
    from app.analysis.legal.compliance_reporter import generate_weekly_report
    return generate_weekly_report()

@app.get("/compliance/report/area/{code}")
def compliance_area_report(code: str):
    """Detailed report for specific compliance area."""
    from app.analysis.legal.compliance_reporter import generate_area_report
    return generate_area_report(code.upper())

@app.get("/compliance/raci")
def compliance_raci(matter_id: int | None = None, area_code: str | None = None):
    """Get RACI matrix entries."""
    from app.analysis.legal.communication_planner import get_raci
    return {"raci": get_raci(matter_id=matter_id, area_code=area_code)}

@app.post("/compliance/raci")
def compliance_set_raci(body: dict):
    """Set RACI entry."""
    from app.analysis.legal.communication_planner import set_raci
    return set_raci(
        area_code=body.get("area_code"),
        matter_id=body.get("matter_id"),
        person_id=body.get("person_id", 0),
        role=body.get("role", "informed"),
        notes=body.get("notes"),
    )

@app.post("/compliance/matters/{matter_id}/communication-plan")
def compliance_comm_plan(matter_id: int):
    """Generate communication plan for matter."""
    from app.analysis.legal_compliance import generate_communication_plan
    return generate_communication_plan(matter_id)

@app.post("/compliance/matters/{matter_id}/execute-communication")
def compliance_exec_comm(matter_id: int):
    """Execute planned communications for matter."""
    from app.analysis.legal_compliance import execute_communication_plan
    return execute_communication_plan(matter_id)


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

@app.get("/costs/budget")
def costs_budget():
    """Current budget status: spend vs limits, alerts today."""
    from app.db.cost_tracker import get_budget_status
    return get_budget_status()


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


# =========================
# Scenario Analyzer endpoints
# =========================

@app.get("/scenarios")
def list_scenarios(status: str | None = None, limit: int = 20):
    from app.analysis.scenario_analyzer import list_scenarios
    return list_scenarios(status=status, limit=limit)

@app.post("/scenarios")
def create_scenario_endpoint(title: str, description: str = "", scenario_type: str = "risk"):
    from app.analysis.scenario_analyzer import create_scenario
    return create_scenario(title=title, description=description, scenario_type=scenario_type)

@app.post("/scenarios/{scenario_id}/analyze")
def analyze_scenario_endpoint(scenario_id: int):
    from app.analysis.scenario_analyzer import analyze_scenario
    return analyze_scenario(scenario_id=scenario_id)

@app.get("/scenarios/compare")
def compare_scenarios_endpoint(ids: str = ""):
    """Compare scenarios. Pass comma-separated IDs."""
    from app.analysis.scenario_analyzer import compare_scenarios
    id_list = [int(x.strip()) for x in ids.split(",") if x.strip().isdigit()]
    return compare_scenarios(scenario_ids=id_list)

@app.post("/scenarios/auto-scan")
def auto_scenario_scan():
    from app.analysis.scenario_analyzer import run_auto_scenarios
    return run_auto_scenarios()


# =========================
# Market Intelligence endpoints
# =========================

@app.get("/market/dashboard")
def market_dashboard(days: int = 7):
    from app.analysis.market_intelligence import get_market_dashboard
    return get_market_dashboard(days=days)

@app.post("/market/scan")
def market_scan():
    from app.analysis.market_intelligence import run_market_scan
    return run_market_scan()

@app.get("/market/insights")
def market_insights(insight_type: str | None = None, min_relevance: int = 0, limit: int = 20):
    from app.analysis.market_intelligence import get_market_insights
    return get_market_insights(insight_type=insight_type, min_relevance=min_relevance, limit=limit)

@app.post("/market/sources")
def add_market_source_endpoint(name: str, url: str, source_type: str = "rss"):
    from app.analysis.market_intelligence import add_market_source
    return add_market_source(name=name, url=url, source_type=source_type)

@app.get("/market/alerts")
def market_alerts(acknowledged: bool = False):
    from app.analysis.market_intelligence import get_market_alerts
    return get_market_alerts(acknowledged=acknowledged)


# =========================
# Competitor Intelligence endpoints
# =========================

@app.get("/competitors")
def competitive_landscape():
    from app.analysis.competitor_intelligence import get_competitive_landscape
    return get_competitive_landscape()

@app.post("/competitors")
def add_competitor_endpoint(name: str, krs_number: str | None = None, industry: str = "energia", watch_level: str = "active"):
    from app.analysis.competitor_intelligence import add_competitor
    return add_competitor(name=name, krs_number=krs_number, industry=industry, watch_level=watch_level)

@app.post("/competitors/scan")
def competitor_scan():
    from app.analysis.competitor_intelligence import run_competitor_scan
    return run_competitor_scan()

@app.get("/competitors/{competitor_id}/analysis")
def competitor_analysis(competitor_id: int):
    from app.analysis.competitor_intelligence import analyze_competitor
    return analyze_competitor(competitor_id=competitor_id)

@app.get("/competitors/signals")
def competitor_signals(competitor_id: int | None = None, signal_type: str | None = None, days: int = 30):
    from app.analysis.competitor_intelligence import get_competitor_signals
    return get_competitor_signals(competitor_id=competitor_id, signal_type=signal_type, days=days)


# =========================
# Process Intelligence endpoints
# =========================

@app.get("/process-intel/dashboard")
def process_intel_dashboard():
    from app.analysis.business_lines import get_business_lines
    from app.analysis.app_inventory import get_app_inventory
    from app.analysis.optimization_planner import get_optimization_dashboard
    result = {
        "business_lines": get_business_lines(),
        "apps": get_app_inventory(),
        "optimizations": get_optimization_dashboard(),
    }
    try:
        from app.analysis.employee_automation import get_automation_overview
        result["workforce_automation"] = get_automation_overview()
    except Exception:
        pass
    try:
        from app.analysis.tech_radar import get_tech_radar_dashboard
        result["tech_radar"] = get_tech_radar_dashboard()
    except Exception:
        pass
    return result

@app.get("/process-intel/business-lines")
def business_lines_endpoint():
    from app.analysis.business_lines import get_business_lines
    return get_business_lines()

@app.post("/process-intel/discover")
def discover_business_lines_endpoint():
    from app.analysis.business_lines import discover_business_lines
    return discover_business_lines(force=True)

@app.get("/process-intel/processes")
def discovered_processes(process_type: str | None = None):
    from app.analysis.process_mining import get_processes
    return get_processes(process_type=process_type)

@app.post("/process-intel/mine")
def mine_processes_endpoint():
    from app.analysis.process_mining import mine_processes
    return mine_processes(force=True)

@app.get("/process-intel/apps")
def app_inventory_endpoint():
    from app.analysis.app_inventory import get_app_inventory
    return get_app_inventory()

@app.post("/process-intel/scan-apps")
def scan_apps_endpoint():
    from app.analysis.app_inventory import scan_applications
    return scan_applications()

@app.get("/process-intel/flows")
def data_flows_endpoint():
    from app.analysis.data_flow_mapper import get_data_flows
    return get_data_flows()

@app.post("/process-intel/map-flows")
def map_flows_endpoint():
    from app.analysis.data_flow_mapper import map_data_flows
    return map_data_flows()

@app.get("/process-intel/optimizations")
def optimizations_endpoint():
    from app.analysis.optimization_planner import get_optimization_dashboard
    return get_optimization_dashboard()

@app.post("/process-intel/plan")
def generate_plans_endpoint():
    from app.analysis.optimization_planner import generate_plans
    return generate_plans()


# F1: Deep App Analysis
@app.post("/process-intel/scan-apps-deep")
def scan_apps_deep_endpoint():
    from app.analysis.app_inventory import scan_applications_deep
    return scan_applications_deep()

@app.get("/process-intel/app-analysis")
def app_analysis_endpoint():
    from app.analysis.app_inventory import get_app_deep_analysis
    return get_app_deep_analysis()

@app.get("/process-intel/app-analysis/{app_id}")
def app_analysis_detail_endpoint(app_id: int):
    from app.analysis.app_inventory import get_app_deep_analysis
    return get_app_deep_analysis(app_id=app_id)

@app.post("/process-intel/app-costs")
def app_costs_endpoint():
    from app.analysis.app_inventory import analyze_app_costs
    return analyze_app_costs()

@app.get("/process-intel/app-replacement-ranking")
def app_replacement_ranking_endpoint():
    from app.analysis.app_inventory import get_app_replacement_ranking
    return get_app_replacement_ranking()


# F2: Employee Automation Analysis (CEO-only)
@app.post("/process-intel/analyze-employee/{person_slug}")
def analyze_employee_endpoint(person_slug: str):
    from app.analysis.employee_automation import analyze_work_profile
    return analyze_work_profile(person_slug)

@app.post("/process-intel/analyze-all-employees")
def analyze_all_employees_endpoint(organization: str | None = None):
    from app.analysis.employee_automation import analyze_all_employees
    return analyze_all_employees(organization=organization)

@app.get("/process-intel/work-profile/{person_slug}")
def work_profile_endpoint(person_slug: str):
    from app.analysis.employee_automation import get_work_profile
    return get_work_profile(person_slug) or {"error": "Profile not found"}

@app.get("/process-intel/automation-overview")
def automation_overview_endpoint():
    from app.analysis.employee_automation import get_automation_overview
    return get_automation_overview()

@app.get("/process-intel/automation-roadmap")
def automation_roadmap_endpoint():
    from app.analysis.employee_automation import get_automation_roadmap
    return get_automation_roadmap()


# F3: Tech Radar
@app.post("/process-intel/discover-tech")
def discover_tech_endpoint():
    from app.analysis.tech_radar import discover_solutions
    return discover_solutions(force=True)

@app.get("/process-intel/tech-radar")
def tech_radar_endpoint():
    from app.analysis.tech_radar import get_tech_radar_dashboard
    return get_tech_radar_dashboard()

@app.get("/process-intel/tech-radar/{solution_id}")
def tech_radar_detail_endpoint(solution_id: int):
    from app.analysis.tech_radar import get_solution_detail
    return get_solution_detail(solution_id) or {"error": "Solution not found"}

@app.get("/process-intel/tech-roadmap")
def tech_roadmap_endpoint():
    from app.analysis.tech_radar import generate_roadmap
    return generate_roadmap()

@app.post("/process-intel/tech-solution/{solution_id}/status")
def tech_solution_status_endpoint(solution_id: int, status: str = "approved"):
    from app.analysis.tech_radar import update_solution_status
    return update_solution_status(solution_id, status)

@app.get("/process-intel/tech-strategic-alignment")
def tech_alignment_endpoint():
    from app.analysis.tech_radar import get_tech_strategic_alignment
    return get_tech_strategic_alignment()
# ── Background Jobs — długie operacje (discover, mine, optimize) ──────────────
import threading
import uuid as _uuid

_bg_jobs: dict[str, dict] = {}  # job_id → {status, progress, result, error}

def _run_in_background(job_id: str, fn, *args, **kwargs):
    """Uruchamia fn w osobnym wątku, śledzi status w _bg_jobs."""
    def _worker():
        try:
            _bg_jobs[job_id]["status"] = "running"
            result = fn(*args, **kwargs)
            _bg_jobs[job_id].update({"status": "done", "result": result})
        except Exception as exc:
            _bg_jobs[job_id].update({"status": "error", "error": str(exc)})
    _bg_jobs[job_id] = {"status": "queued", "progress": "", "result": None, "error": None}
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

@app.post("/process-intel/discover-bg")
def discover_business_lines_bg():
    """Odkrywanie linii biznesowych w tle — zwraca job_id natychmiast."""
    from app.analysis.business_lines import discover_business_lines
    job_id = str(_uuid.uuid4())[:8]
    _run_in_background(job_id, discover_business_lines, True)
    return {"job_id": job_id, "status": "queued", "message": "Odkrywanie uruchomione w tle"}

@app.post("/process-intel/mine-bg")
def mine_processes_bg():
    """Wydobywanie procesów w tle — zwraca job_id natychmiast."""
    from app.analysis.process_mining import mine_processes
    job_id = str(_uuid.uuid4())[:8]
    _run_in_background(job_id, mine_processes, True)
    return {"job_id": job_id, "status": "queued", "message": "Wydobywanie uruchomione w tle"}

@app.post("/process-intel/optimize-bg")
def optimize_processes_bg():
    """Generowanie optymalizacji w tle — zwraca job_id natychmiast."""
    from app.analysis.process_mining import generate_optimizations
    job_id = str(_uuid.uuid4())[:8]
    _run_in_background(job_id, generate_optimizations, True)
    return {"job_id": job_id, "status": "queued", "message": "Optymalizacje generowane w tle"}

@app.get("/process-intel/job/{job_id}")
def get_job_status(job_id: str):
    """Pobierz status background joba."""
    job = _bg_jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    return {"job_id": job_id, **job}
