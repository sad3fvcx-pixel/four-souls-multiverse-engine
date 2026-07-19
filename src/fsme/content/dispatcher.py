# src/fsme/content/dispatcher.py

"""
Content dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from fsme.cards import Card

from .context import ContentContext
from .resolver import ContentResolver
from .result import ContentResult


class ContentDispatcher:
    """
    Dispatches content loading operations.
    """

    def __init__(
        self,
        resolver: ContentResolver | None = None,
    ) -> None:
        self._resolver = resolver or ContentResolver()

    @property
    def resolver(self) -> ContentResolver:
        return self._resolver

    def load_card(
        self,
        context: ContentContext,
        card: Card,
    ) -> ContentResult:
        """
        Dispatch a card loading operation.
        """
        return self._resolver.load_card(
            context=context,
            card=card,
        )

    def unload_card(
        self,
        context: ContentContext,
        card: Card,
    ) -> ContentResult:
        """
        Dispatch a card unloading operation.
        """
        return self._resolver.unload_card(
            context=context,
            card=card,
        )