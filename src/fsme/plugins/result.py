# src/fsme/plugins/result.py

"""
Plugin operation result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PluginResult:
    """
    Result of a plugin operation.
    """

    success: bool = True

    message: str = ""

    loaded_plugins: list[str] = field(default_factory=list)

    unloaded_plugins: list[str] = field(default_factory=list)

    @classmethod
    def ok(
        cls,
        message: str = "",
    ) -> "PluginResult":
        """
        Create a successful plugin result.
        """
        return cls(
            success=True,
            message=message,
        )

    @classmethod
    def failed(
        cls,
        message: str = "",
    ) -> "PluginResult":
        """
        Create a failed plugin result.
        """
        return cls(
            success=False,
            message=message,
        )

    def add_loaded(
        self,
        plugin_id: str,
    ) -> None:
        """
        Record a successfully loaded plugin.
        """
        self.loaded_plugins.append(plugin_id)

    def add_unloaded(
        self,
        plugin_id: str,
    ) -> None:
        """
        Record a successfully unloaded plugin.
        """
        self.unloaded_plugins.append(plugin_id)