# src/fsme/state/roll.py

"""
A dice roll that has happened but has not yet settled.

Four Souls lets players respond to a roll: the die lands, everybody gets the
chance to change or reroll it, and only then does the result count. That gap is
a piece of game state, not a local variable — a game saved mid-roll has to
reload mid-roll — so the roll waits here while the responses resolve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PendingRoll:
    """
    One roll, from the moment it lands to the moment it counts.
    """

    roll_id: str

    sides: int
    natural: int
    value: int

    roller: int | None = None
    attack: bool = False

    continuation: Any = None
    """
    The ability that was rolling, parked until the roll settles.

    Nothing outside the Runtime may look inside it. A combat roll has no
    continuation: the round pushed its own next step onto the stack instead.
    """

    def settle(self, value: int) -> int:
        """
        Fix the roll at a value the die could actually show.
        """
        self.value = max(1, min(self.sides, int(value)))

        return self.value

    def __str__(self) -> str:
        return f"roll of {self.value} (natural {self.natural})"
