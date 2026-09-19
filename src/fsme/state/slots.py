# src/fsme/state/slots.py

"""
The monster area, as a row of slots rather than a heap of monsters.

COMPREHENSIVE_RULES.md §2 lays out the monster area as slots, each holding its
own cards, and calls the face-up card of a slot that slot's active monster.
Most of the time the difference does not show: two slots holding one monster
each look exactly like two monsters. It shows in three places, and all three
are printed on cards.

A monster revealed by attacking the monster deck goes into a slot *on top of*
the monster already there (§7), and when it dies the one underneath is face up
again. A card may name a slot rather than a monster — "attack a monster in one
of these slots" — which is only possible if a slot is something to name. And an
emptied slot refills itself (§9), which is a statement about the slot and not
about the monster that left it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MonsterSlot:
    """
    One place in the monster area, and everything stacked in it.

    The last card is the face-up one. A slot holding nothing is an empty slot,
    which is a real thing to be: the rules fill it, and until they do, it is
    still there.
    """

    cards: list[Any] = field(default_factory=list)

    @property
    def active(self) -> Any | None:
        """
        The face-up monster, which is the one that can be attacked.
        """
        return self.cards[-1] if self.cards else None

    @property
    def is_empty(self) -> bool:
        return not self.cards

    def push(self, card: Any) -> None:
        """
        Put a monster into this slot, face up, over whatever was there.
        """
        self.cards.append(card)

    def remove(self, card: Any) -> bool:
        """
        Take one monster out of this slot, wherever in the pile it was.

        Whatever was under it becomes the active monster again, which is what
        the rules mean by a monster being "on top of" another.
        """
        for index, held in enumerate(self.cards):
            if held is card:
                del self.cards[index]

                return True

        return False

    def __len__(self) -> int:
        return len(self.cards)

    def __str__(self) -> str:
        if not self.cards:
            return "empty slot"

        name = getattr(self.active, "name", "?")
        buried = len(self.cards) - 1

        return f"{name}" if not buried else f"{name} (over {buried})"
