"""Omnius — Corporate AI Agent API.

FastAPI application with RBAC, audit logging, and multi-role access.
Deployed per-company (REF, REH) on company infrastructure.
Controlled by Gilbertus (Sebastian's private mentat) via API key.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

log = structlog.get_logger(__name__)

# ── Config validation ──────────────────────────────────────────────────────

COMPANY = os.getenv("OMNIUS_COMPANY_NAME")
TENANT = os.getenv("OMNIUS_TENANT")

if not COMPANY or not TENANT:
    raise RuntimeError(
        "OMNIUS_COMPANY_NAME and OMNIUS_TENANT must be set in .env. "
        "Example: OMNIUS_COMPANY_NAME='Respect Energy Fuels' OMNIUS_TENANT='ref'"
    )

# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=f"Omnius — {COMPANY}",
    version="0.1.0",
    description=f"Corporate AI Agent for {COMPANY}. Controlled by Gilbertus.",
)


# ── CORS ───────────────────────────────────────────────────────────────────

CORS_ORIGINS = os.getenv("OMNIUS_CORS_ORIGINS", "https://teams.microsoft.com").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["X-API-Key", "Authorization", "Content-Type", "X-Request-ID"],
)


# ── Security headers + Request ID ──────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate or propagate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.state.request_id = request_id

        response: Response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Request-ID"] = request_id
        if os.getenv("OMNIUS_HTTPS", "1") == "1":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


app.add_middleware(SecurityHeadersMiddleware)

# ── Prometheus metrics ─────────────────────────────────────────────────────

try:
    from omnius.api.metrics import MetricsMiddleware, metrics_endpoint
    app.add_middleware(MetricsMiddleware)
    app.add_route("/metrics", metrics_endpoint)
except ImportError:
    pass  # prometheus_client not installed — skip metrics


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check — no auth required."""
    from omnius.db.postgres import get_pg_connection

    checks = {"db": False}

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        checks["db"] = True
    except Exception as e:
        log.error("health_check_db_failed", error=str(e))

    all_ok = all(checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "tenant": TENANT,
        "company": COMPANY,
        "checks": checks,
    }


# ── Status ──────────────────────────────────────────────────────────────────

@app.get("/api/v1/status")
async def status():
    """System status — no auth required (counts only, no sensitive data)."""
    from omnius.db.postgres import get_pg_connection
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM omnius_users WHERE is_active = TRUE")
                users = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM omnius_documents")
                docs = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM omnius_chunks")
                chunks = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM omnius_operator_tasks WHERE status = 'pending'")
                pending_tasks = cur.fetchone()[0]

        return {
            "tenant": TENANT,
            "company": COMPANY,
            "users": users,
            "documents": docs,
            "chunks": chunks,
            "pending_tasks": pending_tasks,
        }
    except Exception as e:
        log.error("status_failed", error=str(e))
        return {"tenant": TENANT, "status": "error"}


# ── Include routers with API versioning ────────────────────────────────────

from omnius.api.routes.ask import router as ask_router
from omnius.api.routes.commands import router as commands_router
from omnius.api.routes.admin import router as admin_router
from omnius.api.routes.plaud import router as plaud_router, webhook_router as plaud_webhook_router

app.include_router(ask_router, prefix="/api/v1")
app.include_router(commands_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(plaud_router, prefix="/api/v1")

# Plaud webhook (no versioning — Plaud sends to fixed URL)
app.include_router(plaud_webhook_router)

# Teams Bot router (no versioning — Bot Framework expects fixed path)
try:
    from omnius.bot.teams_bot import router as teams_router
    app.include_router(teams_router)
except ImportError:
    pass

# ── Static frontend ────────────────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    @app.get("/")
    async def serve_frontend():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/auth/callback")
    async def auth_callback():
        """Azure AD redirect — serve same SPA which handles the hash fragment."""
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
