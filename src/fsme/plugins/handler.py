# src/fsme/plugins/handler.py

"""
Plugin handler for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import PluginContext
from .plugin import Plugin
from .result import PluginResult


class PluginHandler:
    """
    Handles plugin operations.
    """

    def register(
        self,
        context: PluginContext,
        plugin: Plugin,
    ) -> PluginResult:
        """
        Register and load a plugin.
        """
        context.manager.register(plugin)
        plugin.load()

        result = PluginResult.ok()

        result.add_loaded(plugin.id)

        return result

    def unregister(
        self,
        context: PluginContext,
        plugin: Plugin,
    ) -> PluginResult:
        """
        Unregister and unload a plugin.
        """
        plugin.unload()
        context.manager.unregister(plugin.id)

        result = PluginResult.ok()

        result.add_unloaded(plugin.id)

        return result