# src/fsme/config/resolver.py

"""
Configuration resolver for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Any

from .context import ConfigContext
from .handler import ConfigHandler
from .result import ConfigResult


class ConfigResolver:
    """
    Resolves configuration operations.
    """

    def __init__(
        self,
        handler: ConfigHandler | None = None,
    ) -> None:
        self._handler = handler or ConfigHandler()

    @property
    def handler(self) -> ConfigHandler:
        """
        Return the configuration handler.
        """
        return self._handler

    def get(
        self,
        context: ConfigContext,
        key: str,
        default: Any = None,
    ) -> ConfigResult:
        """
        Resolve a configuration lookup.
        """
        return self._handler.get(
            context=context,
            key=key,
            default=default,
        )

    def set(
        self,
        context: ConfigContext,
        key: str,
        value: Any,
    ) -> ConfigResult:
        """
        Resolve a configuration update.
        """
        return self._handler.set(
            context=context,
            key=key,
            value=value,
        )

    def remove(
        self,
        context: ConfigContext,
        key: str,
    ) -> ConfigResult:
        """
        Resolve configuration removal.
        """
        return self._handler.remove(
            context=context,
            key=key,
        )

    def clear(
        self,
        context: ConfigContext,
    ) -> ConfigResult:
        """
        Resolve clearing all configuration values.
        """
        return self._handler.clear(
            context=context,
        )