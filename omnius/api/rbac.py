"""RBAC middleware for Omnius — checks permissions and logs to audit."""
from __future__ import annotations

import json
from functools import wraps
from typing import Any, Callable

import structlog
from fastapi import HTTPException, Request

from omnius.api.auth import authenticate
from omnius.core.permissions import has_permission
from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)


def audit_log(user: dict[str, Any], action: str, resource: str | None = None,
              request_summary: dict | None = None, result_status: str = "ok",
              ip_address: str | None = None):
    """Log action to omnius_audit_log."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO omnius_audit_log
                        (user_id, api_key_id, action, resource, request_summary, result_status, ip_address)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    user.get("user_id"),
                    user.get("api_key_id"),
                    action,
                    resource,
                    json.dumps(request_summary) if request_summary else None,
                    result_status,
                    ip_address,
                ))
            conn.commit()
    except Exception as e:
        log.error("audit_log_failed", error=str(e))


def require_permission(*permissions: str):
    """Decorator for FastAPI route handlers that require specific permissions.

    Usage:
        @router.post("/commands/send_email")
        @require_permission("commands:email")
        async def send_email(request: Request, user: dict = None, ...):
            ...

    The decorator:
    1. Authenticates the request
    2. Checks all required permissions
    3. Logs to audit (success or denied)
    4. Injects `user` dict into kwargs
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = await authenticate(request)
            ip = request.client.host if request.client else None

            # Check all required permissions
            for perm in permissions:
                if not has_permission(user, perm):
                    audit_log(user, func.__name__, resource=perm,
                              result_status="denied", ip_address=ip)
                    log.warning("permission_denied",
                                user=user.get("email", user.get("api_key_name")),
                                permission=perm, endpoint=func.__name__)
                    raise HTTPException(status_code=403,
                                        detail=f"Permission denied: {perm}")

            # Audit success
            audit_log(user, func.__name__, ip_address=ip)

            kwargs["user"] = user
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_auth():
    """Decorator that only authenticates (no permission check). Logs to audit."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = await authenticate(request)
            ip = request.client.host if request.client else None
            audit_log(user, func.__name__, ip_address=ip)
            kwargs["user"] = user
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
