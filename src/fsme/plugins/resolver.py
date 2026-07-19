# src/fsme/plugins/resolver.py

"""
Plugin resolver for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import PluginContext
from .handler import PluginHandler
from .plugin import Plugin
from .result import PluginResult


class PluginResolver:
    """
    Resolves plugin operations.
    """

    def __init__(
        self,
        handler: PluginHandler | None = None,
    ) -> None:
        self._handler = handler or PluginHandler()

    @property
    def handler(self) -> PluginHandler:
        """
        Return the plugin handler.
        """
        return self._handler

    def register(
        self,
        context: PluginContext,
        plugin: Plugin,
    ) -> PluginResult:
        """
        Register a plugin.
        """
        return self._handler.register(
            context=context,
            plugin=plugin,
        )

    def unregister(
        self,
        context: PluginContext,
        plugin: Plugin,
    ) -> PluginResult:
        """
        Unregister a plugin.
        """
        return self._handler.unregister(
            context=context,
            plugin=plugin,
        )