# src/fsme/plugins/manager.py

"""
Plugin manager for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .plugin import Plugin


class PluginManager:
    """
    Manages loaded plugins.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}

    def register(
        self,
        plugin: Plugin,
    ) -> None:
        """
        Register a plugin.
        """
        self._plugins[plugin.id] = plugin

    def unregister(
        self,
        plugin_id: str,
    ) -> None:
        """
        Remove a plugin.
        """
        self._plugins.pop(plugin_id, None)

    def get(
        self,
        plugin_id: str,
    ) -> Plugin | None:
        """
        Return a registered plugin.
        """
        return self._plugins.get(plugin_id)

    def all(self) -> list[Plugin]:
        """
        Return all registered plugins.
        """
        return list(self._plugins.values())

    def clear(self) -> None:
        """
        Remove all registered plugins.
        """
        self._plugins.clear()

    def load_all(self) -> None:
        """
        Load every registered plugin.
        """
        for plugin in self._plugins.values():
            plugin.load()

    def unload_all(self) -> None:
        """
        Unload every registered plugin.
        """
        for plugin in reversed(list(self._plugins.values())):
            plugin.unload()

    def __len__(self) -> int:
        return len(self._plugins)

    def __iter__(self):
        return iter(self._plugins.values())