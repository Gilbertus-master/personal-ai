"""Plugin Runtime Loader — loads active plugins at startup.

Called from omnius/api/main.py after routers are registered.
Each plugin gets its own sub-router under /api/v1/plugins/{name}/.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, APIRouter, Request

from omnius.db.postgres import get_pg_connection
from omnius.plugins.sdk.base import PluginContext

log = structlog.get_logger(__name__)

TENANT = os.getenv("OMNIUS_TENANT", "unknown")
PLUGINS_DIR = Path(__file__).parent / "installed"


def load_plugins(app: FastAPI) -> None:
    """Discover and load all active plugins from the database.

    For each active plugin:
    1. Query DB for plugin metadata
    2. Find handler on filesystem
    3. Import handler module via importlib
    4. Create PluginContext
    5. Register routes under /api/v1/plugins/{name}/
    """
    plugins_loaded = 0
    plugins_failed = 0

    try:
        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, display_name, created_by
                    FROM omnius_plugins
                    WHERE status = 'active'
                    ORDER BY name
                """)
                active_plugins = cur.fetchall()
    except Exception as e:
        log.warning("plugin_loader_db_unavailable", error=str(e))
        return

    for plugin_row in active_plugins:
        plugin_id, plugin_name, display_name, created_by = plugin_row
        try:
            _load_single_plugin(app, plugin_name, created_by or 0)
            plugins_loaded += 1
            log.info("plugin_loaded", plugin=plugin_name)
        except Exception as e:
            plugins_failed += 1
            log.error("plugin_load_failed", plugin=plugin_name, error=str(e))

    # Also try loading sample plugins from the plugins directory
    _load_sample_plugins(app)

    log.info("plugin_loader_complete",
             loaded=plugins_loaded, failed=plugins_failed)


def _load_single_plugin(app: FastAPI, plugin_name: str, user_id: int) -> None:
    """Load a single plugin from the installed directory."""
    plugin_dir = PLUGINS_DIR / plugin_name
    if not plugin_dir.exists():
        log.warning("plugin_dir_missing", plugin=plugin_name, path=str(plugin_dir))
        return

    # Get manifest to find hooks
    manifest_path = plugin_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.json in {plugin_dir}")

    import json
    with open(manifest_path) as f:
        manifest = json.load(f)

    context = PluginContext(tenant=TENANT, user_id=user_id, plugin_name=plugin_name)

    # Register command_handler hooks as routes
    plugin_router = APIRouter(
        prefix=f"/plugins/{plugin_name}",
        tags=[f"plugin:{plugin_name}"],
    )

    for hook in manifest.get("hooks", []):
        if hook["type"] == "command_handler":
            handler_path = hook["handler"]  # e.g. "backend/handler.py:handle_hello"
            action = hook.get("action", "default")
            handler_fn = _import_handler(plugin_dir, handler_path)

            _register_command_route(plugin_router, action, handler_fn, context)

    app.include_router(plugin_router, prefix="/api/v1")


def _load_sample_plugins(app: FastAPI) -> None:
    """Load sample plugins bundled with the codebase (for dev/demo)."""
    samples_base = Path(__file__).parent
    for entry in samples_base.iterdir():
        if entry.is_dir() and entry.name.startswith("sample_"):
            manifest_path = entry / "manifest.json"
            if not manifest_path.exists():
                continue

            plugin_name = entry.name.replace("sample_", "")
            try:
                import json
                with open(manifest_path) as f:
                    manifest = json.load(f)

                context = PluginContext(
                    tenant=TENANT, user_id=0, plugin_name=manifest.get("name", plugin_name),
                )

                plugin_router = APIRouter(
                    prefix=f"/plugins/{manifest.get('name', plugin_name)}",
                    tags=[f"plugin:{manifest.get('name', plugin_name)}"],
                )

                for hook in manifest.get("hooks", []):
                    if hook["type"] == "command_handler":
                        handler_fn = _import_handler(entry, hook["handler"])
                        action = hook.get("action", "default")
                        _register_command_route(plugin_router, action, handler_fn, context)

                app.include_router(plugin_router, prefix="/api/v1")
                log.info("sample_plugin_loaded", plugin=manifest.get("name", plugin_name))
            except Exception as e:
                log.warning("sample_plugin_load_failed", plugin=plugin_name, error=str(e))


def _import_handler(plugin_dir: Path, handler_path: str) -> Any:
    """Import a handler function from a plugin directory.

    handler_path format: "backend/handler.py:handle_hello"
    """
    file_part, func_name = handler_path.rsplit(":", 1)
    full_path = plugin_dir / file_part

    if not full_path.exists():
        raise FileNotFoundError(f"Handler file not found: {full_path}")

    module_name = f"omnius_plugin_{plugin_dir.name}_{func_name}"
    spec = importlib.util.spec_from_file_location(module_name, str(full_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for {full_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    handler_fn = getattr(module, func_name, None)
    if handler_fn is None:
        raise AttributeError(f"Handler function '{func_name}' not found in {full_path}")

    return handler_fn


def _register_command_route(router: APIRouter, action: str,
                            handler_fn: Any, context: PluginContext) -> None:
    """Register GET and POST routes for a command_handler hook."""

    async def _handle_get(request: Request):
        return await handler_fn(context, {})

    async def _handle_post(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        return await handler_fn(context, body)

    # Use unique operation IDs to avoid FastAPI conflicts
    op_prefix = f"plugin_{context.plugin_name}_{action}"
    router.add_api_route(f"/{action}", _handle_get, methods=["GET"],
                         name=f"{op_prefix}_get")
    router.add_api_route(f"/{action}", _handle_post, methods=["POST"],
                         name=f"{op_prefix}_post")
