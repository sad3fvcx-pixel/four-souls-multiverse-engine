# src/fsme/content/resolver.py

"""
Content resolver for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from fsme.cards import Card

from .context import ContentContext
from .handler import ContentHandler
from .result import ContentResult


class ContentResolver:
    """
    Resolves content loading operations through the content handler.
    """

    def __init__(
        self,
        handler: ContentHandler | None = None,
    ) -> None:
        self._handler = handler or ContentHandler()

    @property
    def handler(self) -> ContentHandler:
        return self._handler

    def load_card(
        self,
        context: ContentContext,
        card: Card,
    ) -> ContentResult:
        """
        Load a card into the registry.
        """
        return self._handler.load_card(
            context=context,
            card=card,
        )

    def unload_card(
        self,
        context: ContentContext,
        card: Card,
    ) -> ContentResult:
        """
        Remove a card from the registry.
        """
        return self._handler.unload_card(
            context=context,
            card=card,
        )