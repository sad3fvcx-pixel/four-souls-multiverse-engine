# src/fsme/plugins/dispatcher.py

"""
Plugin dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import PluginContext
from .plugin import Plugin
from .resolver import PluginResolver
from .result import PluginResult


class PluginDispatcher:
    """
    Dispatches plugin operations.
    """

    def __init__(
        self,
        resolver: PluginResolver | None = None,
    ) -> None:
        self._resolver = resolver or PluginResolver()

    @property
    def resolver(self) -> PluginResolver:
        """
        Return the plugin resolver.
        """
        return self._resolver

    def register(
        self,
        context: PluginContext,
        plugin: Plugin,
    ) -> PluginResult:
        """
        Dispatch plugin registration.
        """
        return self._resolver.register(
            context=context,
            plugin=plugin,
        )

    def unregister(
        self,
        context: PluginContext,
        plugin: Plugin,
    ) -> PluginResult:
        """
        Dispatch plugin unregistration.
        """
        return self._resolver.unregister(
            context=context,
            plugin=plugin,
        )