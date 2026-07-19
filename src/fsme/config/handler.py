# src/fsme/config/handler.py

"""
Configuration handler for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Any

from .context import ConfigContext
from .result import ConfigResult


class ConfigHandler:
    """
    Handles configuration operations.
    """

    def get(
        self,
        context: ConfigContext,
        key: str,
        default: Any = None,
    ) -> ConfigResult:
        """
        Return a configuration value.
        """
        value = context.config.get(
            key,
            default,
        )

        return ConfigResult.ok(value=value)

    def set(
        self,
        context: ConfigContext,
        key: str,
        value: Any,
    ) -> ConfigResult:
        """
        Store a configuration value.
        """
        context.config.set(
            key,
            value,
        )

        return ConfigResult.ok(value=value)

    def remove(
        self,
        context: ConfigContext,
        key: str,
    ) -> ConfigResult:
        """
        Remove a configuration value.
        """
        context.config.remove(key)

        return ConfigResult.ok()

    def clear(
        self,
        context: ConfigContext,
    ) -> ConfigResult:
        """
        Remove every configuration value.
        """
        context.config.clear()

        return ConfigResult.ok()