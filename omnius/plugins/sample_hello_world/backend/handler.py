"""Hello World plugin — sample command handler."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omnius.plugins.sdk.base import PluginContext


async def handle_hello(context: "PluginContext", request_data: dict) -> dict:
    """Simple hello handler demonstrating plugin SDK usage."""
    context.log("info", "hello_handler_called", data_keys=list(request_data.keys()))
    name = request_data.get("name", "World")
    return {
        "message": f"Hello from plugin! Tenant: {context.tenant}",
        "greeting": f"Hello, {name}!",
        "plugin": context.plugin_name,
    }
