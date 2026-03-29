"""Plugin Deployment Orchestrator — deploy plugins to all tenants.

Handles:
- Extracting code archives from DB to filesystem
- Per-tenant enable/disable
- Rollback with cleanup
- Health checks
"""
from __future__ import annotations

import io
import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import structlog

from omnius.db.postgres import get_pg_connection

log = structlog.get_logger(__name__)

PLUGINS_DIR = Path(__file__).parent.parent / "plugins" / "installed"
DEFAULT_TENANTS = ["ref", "reh"]


def deploy_plugin(
    plugin_name: str, version: str, tenants: list[str] | None = None
) -> dict:
    """Deploy a plugin version to specified tenants (or all).

    1. Fetch code_archive from omnius_plugin_versions
    2. Extract to PLUGINS_DIR/{plugin_name}/
    3. Enable for each tenant in omnius_plugin_config
    4. Set plugin status to 'active'
    """
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Get plugin ID and version archive
                cur.execute("""
                    SELECT pv.id, pv.code_archive, p.id AS plugin_id
                    FROM omnius_plugin_versions pv
                    JOIN omnius_plugins p ON p.id = pv.plugin_id
                    WHERE p.name = %s AND pv.version = %s
                """, (plugin_name, version))
                row = cur.fetchone()
                if not row:
                    return {
                        "plugin_name": plugin_name,
                        "version": version,
                        "status": "error",
                        "error": f"Plugin version '{plugin_name}@{version}' not found",
                    }

                version_id, code_archive, plugin_id = row

                # Extract code archive to filesystem
                plugin_dir = PLUGINS_DIR / plugin_name
                plugin_dir.mkdir(parents=True, exist_ok=True)

                if code_archive:
                    buf = io.BytesIO(bytes(code_archive))
                    try:
                        with tarfile.open(fileobj=buf, mode="r:*") as tar:
                            tar.extractall(path=str(plugin_dir), filter="data")
                    except Exception as e:
                        log.error("plugin_archive_extract_failed",
                                  plugin=plugin_name, error=str(e))
                        return {
                            "plugin_name": plugin_name,
                            "version": version,
                            "status": "error",
                            "error": f"Failed to extract archive: {e}",
                        }

                # Determine target tenants
                if tenants is None:
                    cur.execute("""
                        SELECT DISTINCT tenant FROM omnius_plugin_config
                        WHERE plugin_id = %s
                    """, (plugin_id,))
                    existing = [r[0] for r in cur.fetchall()]
                    tenants = existing if existing else DEFAULT_TENANTS

                # Enable for each tenant
                now = datetime.now(timezone.utc)
                for tenant in tenants:
                    cur.execute("""
                        INSERT INTO omnius_plugin_config
                            (plugin_id, tenant, enabled, installed_version, installed_at, updated_at)
                        VALUES (%s, %s, TRUE, %s, %s, %s)
                        ON CONFLICT (plugin_id, tenant) DO UPDATE SET
                            enabled = TRUE,
                            installed_version = EXCLUDED.installed_version,
                            installed_at = EXCLUDED.installed_at,
                            updated_at = EXCLUDED.updated_at
                    """, (plugin_id, tenant, version, now, now))

                # Activate plugin
                cur.execute("""
                    UPDATE omnius_plugins
                    SET status = 'active', current_version = %s, updated_at = NOW()
                    WHERE id = %s
                """, (version, plugin_id))

                # Mark version as deployed
                cur.execute("""
                    UPDATE omnius_plugin_versions
                    SET deployed_at = NOW()
                    WHERE id = %s
                """, (version_id,))

            conn.commit()

        log.info("plugin_deployed", plugin=plugin_name, version=version,
                 tenants=tenants)
        return {
            "plugin_name": plugin_name,
            "version": version,
            "deployed_to": tenants,
            "status": "deployed",
        }

    except Exception as e:
        log.error("plugin_deploy_failed", plugin=plugin_name, error=str(e))
        return {
            "plugin_name": plugin_name,
            "version": version,
            "status": "error",
            "error": str(e),
        }


def rollback_plugin(plugin_name: str) -> dict:
    """Rollback a plugin: disable for all tenants and remove files."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Disable plugin
                cur.execute("""
                    UPDATE omnius_plugins
                    SET status = 'disabled', updated_at = NOW()
                    WHERE name = %s
                    RETURNING id
                """, (plugin_name,))
                row = cur.fetchone()
                if not row:
                    return {
                        "plugin_name": plugin_name,
                        "status": "error",
                        "error": f"Plugin '{plugin_name}' not found",
                    }
                plugin_id = row[0]

                # Disable for all tenants
                cur.execute("""
                    UPDATE omnius_plugin_config
                    SET enabled = FALSE, updated_at = NOW()
                    WHERE plugin_id = %s
                """, (plugin_id,))

            conn.commit()

        # Remove plugin directory
        plugin_dir = PLUGINS_DIR / plugin_name
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)

        log.info("plugin_rolled_back", plugin=plugin_name)
        return {"plugin_name": plugin_name, "status": "rolled_back"}

    except Exception as e:
        log.error("plugin_rollback_failed", plugin=plugin_name, error=str(e))
        return {"plugin_name": plugin_name, "status": "error", "error": str(e)}


def check_plugin_health(plugin_name: str) -> dict:
    """Check plugin health: filesystem, manifest, DB status."""
    checks = {}

    # Check filesystem
    plugin_dir = PLUGINS_DIR / plugin_name
    checks["directory_exists"] = plugin_dir.exists()

    # Check manifest
    manifest_path = plugin_dir / "manifest.json"
    checks["manifest_valid"] = False
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                json.load(f)
            checks["manifest_valid"] = True
        except (json.JSONDecodeError, OSError):
            pass

    # Check DB status
    checks["db_active"] = False
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status FROM omnius_plugins WHERE name = %s
                """, (plugin_name,))
                row = cur.fetchone()
                if row and row[0] == "active":
                    checks["db_active"] = True
    except Exception as e:
        log.warning("plugin_health_db_check_failed", plugin=plugin_name,
                    error=str(e))

    healthy = all(checks.values())
    return {"plugin_name": plugin_name, "healthy": healthy, "checks": checks}


def get_deployment_status() -> list[dict]:
    """Get deployment status of all plugins with per-tenant info."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT p.id, p.name, p.current_version, p.status
                    FROM omnius_plugins p
                    ORDER BY p.name
                """)
                plugins = cur.fetchall()

                result = []
                for plugin_id, name, current_version, status in plugins:
                    cur.execute("""
                        SELECT tenant, enabled, installed_version
                        FROM omnius_plugin_config
                        WHERE plugin_id = %s
                        ORDER BY tenant
                    """, (plugin_id,))
                    tenant_rows = cur.fetchall()

                    tenants = [
                        {
                            "tenant": t[0],
                            "enabled": t[1],
                            "installed_version": t[2],
                        }
                        for t in tenant_rows
                    ]

                    result.append({
                        "name": name,
                        "version": current_version,
                        "status": status,
                        "tenants": tenants,
                    })

                return result

    except Exception as e:
        log.error("deployment_status_failed", error=str(e))
        return []
