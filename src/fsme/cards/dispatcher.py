# src/fsme/cards/dispatcher.py

"""
Card dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import CardContext
from .handler import CardHandler
from .resolver import CardResolver
from .result import CardResult


class CardDispatcher:
    """
    Dispatches card operations to the resolver.
    """

    def __init__(
        self,
        resolver: CardResolver | None = None,
    ) -> None:
        self._resolver = resolver or CardResolver()

    @property
    def resolver(self) -> CardResolver:
        return self._resolver

    def dispatch(
        self,
        handler: CardHandler,
        context: CardContext,
    ) -> CardResult:
        """
        Dispatch a card operation for execution.
        """
        return self._resolver.resolve(
            handler,
            context,
        )

    def set_resolver(
        self,
        resolver: CardResolver,
    ) -> None:
        """
        Replace the active resolver.
        """
        self._resolver = resolver