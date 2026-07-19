# src/fsme/plugins/utils.py

"""
Utility helpers for the plugin subsystem.
"""

from __future__ import annotations

from .manager import PluginManager
from .plugin import Plugin


def is_plugin(value: object) -> bool:
    """
    Return True if the value is a Plugin.
    """
    return isinstance(value, Plugin)


def ensure_plugin(value: object) -> Plugin:
    """
    Ensure that the provided value is a Plugin.
    """
    if not isinstance(value, Plugin):
        raise TypeError(
            f"Expected Plugin, got {type(value).__name__}."
        )

    return value


def is_manager(value: object) -> bool:
    """
    Return True if the value is a PluginManager.
    """
    return isinstance(value, PluginManager)


def ensure_manager(value: object) -> PluginManager:
    """
    Ensure that the provided value is a PluginManager.
    """
    if not isinstance(value, PluginManager):
        raise TypeError(
            f"Expected PluginManager, got {type(value).__name__}."
        )

    return value


def plugin_name(plugin: Plugin) -> str:
    """
    Return the plugin class name.
    """
    return plugin.__class__.__name__


def plugin_count(manager: PluginManager) -> int:
    """
    Return the number of registered plugins.
    """
    return len(manager)