# src/fsme/cards/resolver.py

"""
Card resolver for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import CardContext
from .handler import CardHandler
from .result import CardResult


class CardResolver:
    """
    Resolves card operations.

    Concrete card behavior will later be implemented by the
    content pipeline. For now this class provides the common
    interface used by the engine.
    """

    def resolve(
        self,
        handler: CardHandler,
        context: CardContext,
    ) -> CardResult:
        """
        Execute a card operation using the provided handler.
        """
        return handler.execute(context)