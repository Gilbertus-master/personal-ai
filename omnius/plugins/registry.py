"""Plugin Registry — CRUD operations for omnius_plugins table."""
from __future__ import annotations

import hashlib
import json

import structlog

from omnius.db.postgres import get_pg_connection
from omnius.plugins.sdk.manifest import validate_manifest

log = structlog.get_logger(__name__)


def register_plugin(manifest: dict, code_archive: bytes, user_id: int) -> dict:
    """Register a new plugin or add a new version to an existing one.

    Steps:
    1. Validate manifest
    2. Insert/upsert omnius_plugins row
    3. Insert omnius_plugin_versions row
    4. Write code_archive to filesystem (if provided)

    Returns: {"status": "registered", "plugin_id": int, "version": str}
             or {"status": "error", "error": str}
    """
    validation = validate_manifest(manifest)
    if not validation["valid"]:
        return {"status": "error", "error": f"Invalid manifest: {validation['error']}"}

    name = manifest["name"]
    version = manifest["version"]
    code_hash = hashlib.sha256(code_archive).hexdigest() if code_archive else "empty"

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                # Upsert plugin record
                cur.execute("""
                    INSERT INTO omnius_plugins
                        (name, display_name, description, author, status,
                         current_version, permissions_required, config_schema, created_by)
                    VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        description = EXCLUDED.description,
                        author = EXCLUDED.author,
                        current_version = EXCLUDED.current_version,
                        permissions_required = EXCLUDED.permissions_required,
                        config_schema = EXCLUDED.config_schema,
                        updated_at = NOW()
                    RETURNING id
                """, (
                    name,
                    manifest.get("display_name", name),
                    manifest.get("description", ""),
                    manifest.get("author", "unknown"),
                    version,
                    manifest.get("permissions_required"),
                    json.dumps(manifest.get("config_schema")) if manifest.get("config_schema") else None,
                    user_id,
                ))
                plugin_id = cur.fetchone()[0]

                # Insert version record
                cur.execute("""
                    INSERT INTO omnius_plugin_versions
                        (plugin_id, version, manifest, code_archive, code_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (plugin_id, version) DO UPDATE SET
                        manifest = EXCLUDED.manifest,
                        code_archive = EXCLUDED.code_archive,
                        code_hash = EXCLUDED.code_hash,
                        created_at = NOW()
                    RETURNING id
                """, (
                    plugin_id,
                    version,
                    json.dumps(manifest),
                    code_archive if code_archive else None,
                    code_hash,
                ))
                version_id = cur.fetchone()[0]

            conn.commit()

        log.info("plugin_registered", name=name, version=version,
                 plugin_id=plugin_id, by=user_id)
        return {
            "status": "registered",
            "plugin_id": plugin_id,
            "version_id": version_id,
            "version": version,
        }

    except Exception as e:
        log.error("plugin_register_failed", name=name, error=str(e))
        return {"status": "error", "error": str(e)}


def list_plugins() -> list[dict]:
    """List all registered plugins."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT p.id, p.name, p.display_name, p.description,
                           p.author, p.status, p.current_version,
                           p.permissions_required, p.created_at, p.updated_at
                    FROM omnius_plugins p
                    ORDER BY p.name
                """)
                return [
                    {
                        "id": r[0], "name": r[1], "display_name": r[2],
                        "description": r[3], "author": r[4], "status": r[5],
                        "current_version": r[6], "permissions_required": r[7],
                        "created_at": str(r[8]), "updated_at": str(r[9]),
                    }
                    for r in cur.fetchall()
                ]
    except Exception as e:
        log.error("plugin_list_failed", error=str(e))
        return []


def get_plugin(name: str) -> dict | None:
    """Get a single plugin by name, including version history."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT p.id, p.name, p.display_name, p.description,
                           p.author, p.status, p.current_version,
                           p.permissions_required, p.config_schema,
                           p.created_at, p.updated_at
                    FROM omnius_plugins p
                    WHERE p.name = %s
                """, (name,))
                row = cur.fetchone()
                if not row:
                    return None

                plugin = {
                    "id": row[0], "name": row[1], "display_name": row[2],
                    "description": row[3], "author": row[4], "status": row[5],
                    "current_version": row[6], "permissions_required": row[7],
                    "config_schema": row[8],
                    "created_at": str(row[9]), "updated_at": str(row[10]),
                }

                # Get version history
                cur.execute("""
                    SELECT version, review_status, reviewed_by,
                           reviewed_at, deployed_at, created_at
                    FROM omnius_plugin_versions
                    WHERE plugin_id = %s
                    ORDER BY created_at DESC
                """, (row[0],))
                plugin["versions"] = [
                    {
                        "version": v[0], "review_status": v[1],
                        "reviewed_by": v[2],
                        "reviewed_at": str(v[3]) if v[3] else None,
                        "deployed_at": str(v[4]) if v[4] else None,
                        "created_at": str(v[5]),
                    }
                    for v in cur.fetchall()
                ]

                return plugin
    except Exception as e:
        log.error("plugin_get_failed", name=name, error=str(e))
        return None


def enable_plugin(name: str) -> dict:
    """Set plugin status to 'active'."""
    return _set_status(name, "active")


def disable_plugin(name: str) -> dict:
    """Set plugin status to 'disabled'."""
    return _set_status(name, "disabled")


def _set_status(name: str, status: str) -> dict:
    """Update plugin status."""
    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE omnius_plugins
                    SET status = %s, updated_at = NOW()
                    WHERE name = %s
                    RETURNING id, name, status
                """, (status, name))
                row = cur.fetchone()
                if not row:
                    return {"status": "error", "error": f"Plugin '{name}' not found"}
            conn.commit()

        log.info("plugin_status_changed", name=name, new_status=status)
        return {"status": "ok", "plugin": row[1], "new_status": row[2]}
    except Exception as e:
        log.error("plugin_status_change_failed", name=name, error=str(e))
        return {"status": "error", "error": str(e)}
