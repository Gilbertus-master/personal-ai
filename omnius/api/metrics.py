"""Prometheus metrics for Omnius.

Tracks: request duration, error rates, DB latency, LLM calls, sync stats.
Exposed at /metrics endpoint.
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

# ── Metrics ─────────────────────────────────────────────────────────────────

REQUEST_DURATION = Histogram(
    "omnius_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint", "status"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUEST_COUNT = Counter(
    "omnius_requests_total",
    "Total request count",
    ["method", "endpoint", "status"],
)

ERROR_COUNT = Counter(
    "omnius_errors_total",
    "Total error count",
    ["endpoint", "error_type"],
)

LLM_CALLS = Counter(
    "omnius_llm_calls_total",
    "LLM API calls",
    ["model", "endpoint"],
)

LLM_DURATION = Histogram(
    "omnius_llm_duration_seconds",
    "LLM call duration",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

LLM_TOKENS = Counter(
    "omnius_llm_tokens_total",
    "LLM tokens used",
    ["model", "type"],  # type: input, output
)

DB_QUERY_DURATION = Histogram(
    "omnius_db_query_seconds",
    "Database query duration",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

ACTIVE_USERS = Gauge(
    "omnius_active_users",
    "Active users (queried in last hour)",
)

DOCUMENTS_TOTAL = Gauge(
    "omnius_documents_total",
    "Total documents in system",
)

CHUNKS_TOTAL = Gauge(
    "omnius_chunks_total",
    "Total chunks in system",
)

SYNC_RUNS = Counter(
    "omnius_sync_runs_total",
    "Sync operations",
    ["source", "status"],
)

AUTH_ATTEMPTS = Counter(
    "omnius_auth_attempts_total",
    "Authentication attempts",
    ["method", "result"],  # method: api_key, azure_ad, dev; result: success, failure
)


# ── Middleware ──────────────────────────────────────────────────────────────

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        endpoint = request.url.path
        method = request.method
        status = str(response.status_code)

        REQUEST_DURATION.labels(method=method, endpoint=endpoint, status=status).observe(duration)
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()

        if response.status_code >= 400:
            ERROR_COUNT.labels(endpoint=endpoint, error_type=status).inc()

        return response


# ── Endpoint ────────────────────────────────────────────────────────────────

async def metrics_endpoint(request: Request) -> Response:
    """Prometheus metrics endpoint."""
    # Update gauge metrics
    try:
        from omnius.db.postgres import get_pg_connection
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM omnius_documents")
                DOCUMENTS_TOTAL.set(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM omnius_chunks")
                CHUNKS_TOTAL.set(cur.fetchone()[0])
    except Exception:
        pass

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
