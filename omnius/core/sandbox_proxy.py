"""Sandbox Proxy — forwards Claude API requests from sandbox containers.

Runs as a separate FastAPI service on port 8099. Injects the real
ANTHROPIC_API_KEY, enforces rate limits and cost caps per session,
and logs all usage for audit.

Only reachable from the internal sandbox-net Docker network.
"""
from __future__ import annotations

import os
from collections import defaultdict

import httpx
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = "https://api.anthropic.com"
MAX_REQUESTS_PER_SESSION = 50
MAX_COST_PER_SESSION_USD = 2.00

# In-memory rate counters (reset on restart, DB is source of truth)
_session_counters: dict[str, dict] = defaultdict(
    lambda: {"calls": 0, "cost_usd": 0.0}
)

app = FastAPI(title="Omnius Sandbox Proxy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


def _estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Estimate cost in USD based on token counts and model."""
    # Pricing per 1M tokens (approximate, Haiku)
    if "haiku" in model:
        return (input_tokens * 0.25 + output_tokens * 1.25) / 1_000_000
    elif "sonnet" in model:
        return (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000
    elif "opus" in model:
        return (input_tokens * 15.0 + output_tokens * 75.0) / 1_000_000
    # Default to Haiku pricing
    return (input_tokens * 0.25 + output_tokens * 1.25) / 1_000_000


@app.post("/v1/messages")
async def proxy_messages(request: Request):
    """Forward a messages request to Anthropic API with key injection."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="API key not configured")

    # Get session ID from header or body
    session_id = request.headers.get("X-Sandbox-Session", "unknown")
    body = await request.json()

    # Also check metadata for session_id
    metadata = body.pop("metadata", {})
    if session_id == "unknown" and "session_id" in metadata:
        session_id = metadata["session_id"]

    # Rate limiting: check counters
    counters = _session_counters[session_id]
    if counters["calls"] >= MAX_REQUESTS_PER_SESSION:
        log.warning("sandbox_proxy_rate_limit", session_id=session_id,
                     calls=counters["calls"])
        raise HTTPException(
            status_code=429,
            detail=f"Session rate limit exceeded ({MAX_REQUESTS_PER_SESSION} requests max)",
        )
    if counters["cost_usd"] >= MAX_COST_PER_SESSION_USD:
        log.warning("sandbox_proxy_cost_limit", session_id=session_id,
                     cost=counters["cost_usd"])
        raise HTTPException(
            status_code=429,
            detail=f"Session cost limit exceeded (${MAX_COST_PER_SESSION_USD:.2f} max)",
        )

    # Forward to Anthropic
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{ANTHROPIC_BASE_URL}/v1/messages",
                json=body,
                headers=headers,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream API timeout")
    except httpx.RequestError as e:
        log.error("sandbox_proxy_upstream_error", error=str(e))
        raise HTTPException(status_code=502, detail="Upstream API error")

    if resp.status_code != 200:
        return JSONResponse(
            status_code=resp.status_code,
            content=resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"error": resp.text},
        )

    result = resp.json()

    # Extract token usage
    usage = result.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    model = body.get("model", "claude-haiku-4-5")
    estimated_cost = _estimate_cost(input_tokens, output_tokens, model)

    # Update in-memory counters
    counters["calls"] += 1
    counters["cost_usd"] += estimated_cost

    # Update DB metrics
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omnius_sandbox_sessions
                    SET api_calls_count = api_calls_count + 1,
                        api_cost_usd = api_cost_usd + %s
                    WHERE id = %s
                """, (estimated_cost, session_id))
            conn.commit()
    except Exception as db_err:
        log.error("sandbox_proxy_db_update_failed", error=str(db_err))

    log.info("sandbox_proxy_request",
             session_id=session_id,
             model=model,
             input_tokens=input_tokens,
             output_tokens=output_tokens,
             cost_usd=round(estimated_cost, 6),
             total_calls=counters["calls"],
             total_cost=round(counters["cost_usd"], 4))

    return JSONResponse(content=result)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "sandbox-proxy"}
