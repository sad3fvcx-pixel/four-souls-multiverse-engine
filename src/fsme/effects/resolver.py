# src/fsme/effects/resolver.py

"""
Effect resolver for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import EffectContext
from .handler import EffectHandler
from .result import EffectResult


class EffectResolver:
    """
    Resolves executable effects.

    Concrete effect implementations will later be registered
    through the content pipeline. For now this class provides
    the common interface used by the engine.
    """

    def resolve(
        self,
        handler: EffectHandler,
        context: EffectContext,
    ) -> EffectResult:
        """
        Execute an effect using the provided handler.
        """
        return handler.execute(context)