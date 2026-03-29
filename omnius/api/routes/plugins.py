"""Omnius /admin/plugins/* and /plugins/* endpoints — plugin management and runtime."""
from __future__ import annotations


import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from omnius.api.rbac import audit_log, require_permission
from omnius.plugins.registry import (
    disable_plugin,
    enable_plugin,
    get_plugin,
    list_plugins,
    register_plugin,
)

log = structlog.get_logger(__name__)
router = APIRouter(tags=["plugins"])


# ── Pydantic models ───────────────────────────────────────────────────────

class RegisterPluginRequest(BaseModel):
    manifest: dict
    code_archive_b64: str | None = None  # base64-encoded archive


class UpdatePluginStatusRequest(BaseModel):
    action: str  # "enable" or "disable"


# ── Admin endpoints (/admin/plugins) ──────────────────────────────────────

@router.get("/admin/plugins")
@require_permission("config:write:system")
async def admin_list_plugins(request: Request, user: dict = None):
    """List all registered plugins."""
    audit_log(user, "admin_list_plugins", ip_address=_client_ip(request))
    return {"plugins": list_plugins()}


@router.get("/admin/plugins/{name}")
@require_permission("config:write:system")
async def admin_get_plugin(request: Request, name: str, user: dict = None):
    """Get plugin details including version history."""
    audit_log(user, "admin_get_plugin", resource=name,
              ip_address=_client_ip(request))
    plugin = get_plugin(name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    return plugin


@router.post("/admin/plugins")
@require_permission("config:write:system")
async def admin_register_plugin(request: Request, body: RegisterPluginRequest,
                                user: dict = None):
    """Register a new plugin. Requires gilbertus_admin (role_level >= 99)."""
    # Extra check: only gilbertus_admin can register plugins
    if user.get("role_level", 0) < 99:
        audit_log(user, "admin_register_plugin", result_status="denied",
                  ip_address=_client_ip(request))
        raise HTTPException(status_code=403,
                            detail="Only gilbertus_admin can register plugins")

    code_bytes = b""
    if body.code_archive_b64:
        import base64
        try:
            code_bytes = base64.b64decode(body.code_archive_b64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 in code_archive_b64")

    result = register_plugin(
        manifest=body.manifest,
        code_archive=code_bytes,
        user_id=user.get("user_id", 0),
    )

    audit_log(user, "admin_register_plugin", resource=body.manifest.get("name"),
              request_summary={"version": body.manifest.get("version")},
              result_status=result["status"], ip_address=_client_ip(request))

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.patch("/admin/plugins/{name}")
@require_permission("config:write:system")
async def admin_update_plugin(request: Request, name: str,
                              body: UpdatePluginStatusRequest, user: dict = None):
    """Enable or disable a plugin. Requires gilbertus_admin (role_level >= 99)."""
    if user.get("role_level", 0) < 99:
        audit_log(user, "admin_update_plugin", resource=name,
                  result_status="denied", ip_address=_client_ip(request))
        raise HTTPException(status_code=403,
                            detail="Only gilbertus_admin can manage plugin status")

    if body.action == "enable":
        result = enable_plugin(name)
    elif body.action == "disable":
        result = disable_plugin(name)
    else:
        raise HTTPException(status_code=400,
                            detail=f"Invalid action: {body.action}. Use 'enable' or 'disable'.")

    audit_log(user, "admin_update_plugin", resource=name,
              request_summary={"action": body.action},
              result_status=result["status"], ip_address=_client_ip(request))

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Runtime endpoints (/plugins/{name}/{action}) ─────────────────────────
# These are thin dispatchers; actual plugin routes are registered by loader.py
# These catch-all routes handle plugins:use permission check for runtime calls.

@router.get("/plugins/{name}/{action}")
@require_permission("plugins:use")
async def plugin_runtime_get(request: Request, name: str, action: str,
                             user: dict = None):
    """Runtime GET endpoint for plugins. Dispatches to loaded plugin handler."""
    # The actual plugin routes are registered by loader.py under /api/v1/plugins/{name}/{action}
    # This fallback handles the case where a plugin is not loaded
    raise HTTPException(status_code=404,
                        detail=f"Plugin '{name}' action '{action}' not found or not loaded")


@router.post("/plugins/{name}/{action}")
@require_permission("plugins:use")
async def plugin_runtime_post(request: Request, name: str, action: str,
                              user: dict = None):
    """Runtime POST endpoint for plugins. Dispatches to loaded plugin handler."""
    raise HTTPException(status_code=404,
                        detail=f"Plugin '{name}' action '{action}' not found or not loaded")


def _client_ip(request: Request) -> str | None:
    """Extract client IP from request."""
    return request.client.host if request.client else None
