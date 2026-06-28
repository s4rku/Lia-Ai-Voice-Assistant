"""
Unit tests for the plugin system.
"""
import pytest
from typing import Any

from assistant.plugins.base import Plugin, PluginManager


class EchoPlugin(Plugin):
    name = "echo"
    version = "1.0.0"
    handles = ["say_hello", "say_bye"]

    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any] | None:
        return {"response": f"Echo: {intent}"}


@pytest.mark.asyncio
async def test_plugin_register_and_dispatch():
    pm = PluginManager()
    pm.register(EchoPlugin())

    result = await pm.dispatch("say_hello", {})
    assert result is not None
    assert result["response"] == "Echo: say_hello"


@pytest.mark.asyncio
async def test_plugin_unknown_intent_returns_none():
    pm = PluginManager()
    pm.register(EchoPlugin())

    result = await pm.dispatch("unknown_intent", {})
    assert result is None


@pytest.mark.asyncio
async def test_plugin_loaded_list():
    pm = PluginManager()
    pm.register(EchoPlugin())
    assert "echo" in pm.loaded
