# src/fsme/effects/handler.py

"""
Effect handler protocol for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Protocol

from .context import EffectContext
from .result import EffectResult


class EffectHandler(Protocol):
    """
    Protocol implemented by all effect handlers.
    """

    def execute(
        self,
        context: EffectContext,
    ) -> EffectResult:
        """
        Execute an effect.
        """
        ...