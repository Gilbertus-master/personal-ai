"""Tests for the hello-world plugin handler."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class TestHelloHandler(unittest.TestCase):
    """Test hello-world plugin handler."""

    def test_handle_hello_default(self):
        """handle_hello returns expected greeting with default name."""
        from omnius.plugins.sample_hello_world.backend.handler import handle_hello

        # Create a mock PluginContext
        ctx = MagicMock()
        ctx.tenant = "test-tenant"
        ctx.plugin_name = "hello-world"
        ctx.log = MagicMock()

        result = asyncio.get_event_loop().run_until_complete(
            handle_hello(ctx, {})
        )

        self.assertEqual(result["message"], "Hello from plugin! Tenant: test-tenant")
        self.assertEqual(result["greeting"], "Hello, World!")
        self.assertEqual(result["plugin"], "hello-world")

    def test_handle_hello_with_name(self):
        """handle_hello uses provided name."""
        from omnius.plugins.sample_hello_world.backend.handler import handle_hello

        ctx = MagicMock()
        ctx.tenant = "ref"
        ctx.plugin_name = "hello-world"
        ctx.log = MagicMock()

        result = asyncio.get_event_loop().run_until_complete(
            handle_hello(ctx, {"name": "Sebastian"})
        )

        self.assertEqual(result["greeting"], "Hello, Sebastian!")


if __name__ == "__main__":
    unittest.main()
