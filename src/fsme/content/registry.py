# src/fsme/content/registry.py

"""
Content registry for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Iterable

from fsme.cards import Card


class ContentRegistry:
    """
    Registry containing all loaded game content.
    """

    def __init__(self) -> None:
        self._cards: dict[str, Card] = {}

    def register(self, card: Card) -> None:
        """
        Register a card.
        """
        self._cards[card.card_id] = card

    def unregister(self, card_id: str) -> None:
        """
        Remove a card from the registry.
        """
        self._cards.pop(card_id, None)

    def get(self, card_id: str) -> Card | None:
        """
        Return a registered card.
        """
        return self._cards.get(card_id)

    def all(self) -> list[Card]:
        """
        Return all registered cards.
        """
        return list(self._cards.values())

    def clear(self) -> None:
        """
        Remove every registered card.
        """
        self._cards.clear()

    def __len__(self) -> int:
        return len(self._cards)

    def __iter__(self) -> Iterable[Card]:
        return iter(self._cards.values())