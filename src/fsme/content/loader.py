# src/fsme/content/loader.py

"""
Content loader for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from fsme.cards import Card

from .registry import ContentRegistry


class ContentLoader:
    """
    Loads game content into a registry.
    """

    def __init__(
        self,
        registry: ContentRegistry | None = None,
    ) -> None:
        self._registry = registry or ContentRegistry()

    @property
    def registry(self) -> ContentRegistry:
        return self._registry

    def load_card(self, card: Card) -> None:
        """
        Load a single card.
        """
        self._registry.register(card)

    def unload_card(self, card: Card) -> None:
        """
        Remove a previously loaded card.
        """
        self._registry.unregister(card.card_id)

    def clear(self) -> None:
        """
        Remove all loaded content.
        """
        self._registry.clear()