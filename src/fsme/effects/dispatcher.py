# src/fsme/effects/dispatcher.py

"""
Effect dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import EffectContext
from .handler import EffectHandler
from .resolver import EffectResolver
from .result import EffectResult


class EffectDispatcher:
    """
    Dispatches effects to the resolver.
    """

    def __init__(
        self,
        resolver: EffectResolver | None = None,
    ) -> None:
        self._resolver = resolver or EffectResolver()

    @property
    def resolver(self) -> EffectResolver:
        return self._resolver

    def dispatch(
        self,
        handler: EffectHandler,
        context: EffectContext,
    ) -> EffectResult:
        """
        Dispatch an effect for execution.
        """
        return self._resolver.resolve(
            handler,
            context,
        )

    def set_resolver(
        self,
        resolver: EffectResolver,
    ) -> None:
        """
        Replace the active resolver.
        """
        self._resolver = resolver