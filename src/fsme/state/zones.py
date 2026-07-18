# src/fsme/state/zones.py

"""
Zone definitions for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Generic, Iterator, TypeVar

T = TypeVar("T")


class ZoneType(Enum):
    """
    Types of game zones.
    """

    DECK = auto()
    DISCARD = auto()
    HAND = auto()
    BOARD = auto()
    SHOP = auto()
    TREASURE = auto()
    SOUL = auto()
    MONSTER = auto()
    ROOM = auto()

    def __str__(self) -> str:
        return self.name.lower()


@dataclass(slots=True)
class Zone(Generic[T]):
    """
    Generic ordered card container.

    A Zone does not implement any game rules.
    It only stores objects while preserving order.
    """

    zone_type: ZoneType
    cards: list[T] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self) -> Iterator[T]:
        return iter(self.cards)

    def __bool__(self) -> bool:
        return bool(self.cards)

    def top(self) -> T:
        """
        Return the top card without removing it.
        """
        if not self.cards:
            raise IndexError("zone is empty")
        return self.cards[-1]

    def bottom(self) -> T:
        """
        Return the bottom card without removing it.
        """
        if not self.cards:
            raise IndexError("zone is empty")
        return self.cards[0]

    def draw(self) -> T:
        """
        Remove and return the top card.
        """
        if not self.cards:
            raise IndexError("zone is empty")
        return self.cards.pop()

    def add_top(self, card: T) -> None:
        """
        Put a card on top of the zone.
        """
        self.cards.append(card)

    def add_bottom(self, card: T) -> None:
        """
        Put a card on the bottom of the zone.
        """
        self.cards.insert(0, card)

    def clear(self) -> None:
        """
        Remove all cards.
        """
        self.cards.clear()