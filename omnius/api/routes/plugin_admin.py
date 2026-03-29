"""Omnius /admin/plugins/* — Plugin deployment management endpoints."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from omnius.api.rbac import audit_log, require_permission
from omnius.core.plugin_deployer import (
    check_plugin_health,
    deploy_plugin,
    get_deployment_status,
    rollback_plugin,
)
from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/admin/plugins", tags=["plugin-admin"])


# ── Models ────────────────────────────────────────────────────────────────────

class DeployRequest(BaseModel):
    version: str
    tenants: list[str] | None = None


class TenantRequest(BaseModel):
    tenant: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/installed")
@require_permission("config:write:system")
async def list_installed(request: Request, user: dict = None):
    """List installed plugins with per-tenant status."""
    return {"plugins": get_deployment_status()}


@router.post("/{name}/deploy")
@require_permission("config:write:system")
async def deploy(request: Request, name: str, body: DeployRequest,
                 user: dict = None):
    """Deploy a plugin version to tenants. Requires gilbertus_admin."""
    if user.get("role_level", 0) < 99:
        raise HTTPException(status_code=403,
                            detail="Only gilbertus_admin can deploy plugins")

    result = deploy_plugin(name, body.version, body.tenants)

    ip = request.client.host if request.client else None
    audit_log(user, "plugin_deploy", resource=name,
              request_summary={"version": body.version, "tenants": body.tenants},
              result_status=result.get("status", "unknown"), ip_address=ip)

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error", "Deploy failed"))

    return result


@router.post("/{name}/rollback")
@require_permission("config:write:system")
async def rollback(request: Request, name: str, user: dict = None):
    """Rollback a plugin. Requires gilbertus_admin."""
    if user.get("role_level", 0) < 99:
        raise HTTPException(status_code=403,
                            detail="Only gilbertus_admin can rollback plugins")

    result = rollback_plugin(name)

    ip = request.client.host if request.client else None
    audit_log(user, "plugin_rollback", resource=name,
              result_status=result.get("status", "unknown"), ip_address=ip)

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error", "Rollback failed"))

    return result


@router.post("/{name}/enable")
@require_permission("config:write:system")
async def enable_for_tenant(request: Request, name: str, body: TenantRequest,
                            user: dict = None):
    """Enable plugin for a specific tenant."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omnius_plugin_config pc
                    SET enabled = TRUE, updated_at = NOW()
                    FROM omnius_plugins p
                    WHERE pc.plugin_id = p.id
                      AND p.name = %s
                      AND pc.tenant = %s
                    RETURNING p.name, pc.tenant
                """, (name, body.tenant))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Plugin '{name}' config for tenant '{body.tenant}' not found")
            conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("plugin_enable_failed", plugin=name, tenant=body.tenant,
                  error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    ip = request.client.host if request.client else None
    audit_log(user, "plugin_enable", resource=name,
              request_summary={"tenant": body.tenant}, ip_address=ip)

    return {"plugin_name": name, "tenant": body.tenant, "enabled": True}


@router.post("/{name}/disable")
@require_permission("config:write:system")
async def disable_for_tenant(request: Request, name: str, body: TenantRequest,
                             user: dict = None):
    """Disable plugin for a specific tenant."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omnius_plugin_config pc
                    SET enabled = FALSE, updated_at = NOW()
                    FROM omnius_plugins p
                    WHERE pc.plugin_id = p.id
                      AND p.name = %s
                      AND pc.tenant = %s
                    RETURNING p.name, pc.tenant
                """, (name, body.tenant))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Plugin '{name}' config for tenant '{body.tenant}' not found")
            conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        log.error("plugin_disable_failed", plugin=name, tenant=body.tenant,
                  error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

    ip = request.client.host if request.client else None
    audit_log(user, "plugin_disable", resource=name,
              request_summary={"tenant": body.tenant}, ip_address=ip)

    return {"plugin_name": name, "tenant": body.tenant, "enabled": False}


@router.get("/{name}/health")
@require_permission("config:write:system")
async def health_check(request: Request, name: str, user: dict = None):
    """Check plugin health."""
    return check_plugin_health(name)
