"""
Plugin base class and registry.
Third-party / built-in plugins subclass Plugin and register via PluginManager.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger


class Plugin(ABC):
    """
    Every lia plugin must subclass this.

    Plugins receive intents from the AI layer and return a result dict
    or None if they don't handle the intent.
    """

    name: str = "unnamed_plugin"
    version: str = "0.1.0"
    description: str = ""
    # List of intent names this plugin handles, e.g. ["play_music", "pause_music"]
    handles: list[str] = []

    async def setup(self) -> None:
        """Called once when the plugin is loaded. Override for init work."""

    async def teardown(self) -> None:
        """Called on shutdown. Override for cleanup."""

    @abstractmethod
    async def execute(self, intent: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """
        Handle the intent.
        Return a dict with at least {"response": str} or None to pass through.
        """


class PluginManager:
    """Discovers, loads, and dispatches to plugins."""

    def __init__(self) -> None:
        self._plugins: list[Plugin] = []
        self._intent_map: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        self._plugins.append(plugin)
        for intent in plugin.handles:
            if intent in self._intent_map:
                logger.warning(
                    "Intent '{}' already handled by '{}'. Overriding with '{}'.",
                    intent, self._intent_map[intent].name, plugin.name,
                )
            self._intent_map[intent] = plugin
        logger.info("Plugin registered: {} v{}", plugin.name, plugin.version)

    async def setup_all(self) -> None:
        for plugin in self._plugins:
            try:
                await plugin.setup()
            except Exception:
                logger.exception("Plugin setup failed: {}", plugin.name)

    async def teardown_all(self) -> None:
        for plugin in self._plugins:
            try:
                await plugin.teardown()
            except Exception:
                logger.exception("Plugin teardown failed: {}", plugin.name)

    async def dispatch(self, intent: str, params: dict[str, Any]) -> dict[str, Any] | None:
        plugin = self._intent_map.get(intent)
        if plugin is None:
            return None
        try:
            return await plugin.execute(intent, params)
        except Exception:
            logger.exception("Plugin '{}' raised error for intent '{}'", plugin.name, intent)
            return {"response": f"Plugin error while handling '{intent}'."}

    @property
    def loaded(self) -> list[str]:
        return [p.name for p in self._plugins]


# Global singleton
plugin_manager: PluginManager = PluginManager()
