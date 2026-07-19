# src/fsme/content/handler.py

"""
Content handler for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from fsme.cards import Card

from .context import ContentContext
from .result import ContentResult


class ContentHandler:
    """
    Handles content loading operations.
    """

    def load_card(
        self,
        context: ContentContext,
        card: Card,
    ) -> ContentResult:
        """
        Register a card in the content registry.
        """
        context.registry.register(card)

        result = ContentResult.ok()

        result.loaded_cards.append(card.card_id)

        return result

    def unload_card(
        self,
        context: ContentContext,
        card: Card,
    ) -> ContentResult:
        """
        Remove a card from the content registry.
        """
        context.registry.unregister(card.card_id)

        return ContentResult.ok()