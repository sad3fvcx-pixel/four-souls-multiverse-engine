# src/fsme/config/dispatcher.py

"""
Configuration dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Any

from .context import ConfigContext
from .resolver import ConfigResolver
from .result import ConfigResult


class ConfigDispatcher:
    """
    Dispatches configuration operations.
    """

    def __init__(
        self,
        resolver: ConfigResolver | None = None,
    ) -> None:
        self._resolver = resolver or ConfigResolver()

    @property
    def resolver(self) -> ConfigResolver:
        """
        Return the configuration resolver.
        """
        return self._resolver

    def get(
        self,
        context: ConfigContext,
        key: str,
        default: Any = None,
    ) -> ConfigResult:
        """
        Dispatch a configuration lookup.
        """
        return self._resolver.get(
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
        Dispatch a configuration update.
        """
        return self._resolver.set(
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
        Dispatch configuration removal.
        """
        return self._resolver.remove(
            context=context,
            key=key,
        )

    def clear(
        self,
        context: ConfigContext,
    ) -> ConfigResult:
        """
        Dispatch clearing all configuration values.
        """
        return self._resolver.clear(
            context=context,
        )