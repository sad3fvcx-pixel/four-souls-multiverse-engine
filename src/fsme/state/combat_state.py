# src/fsme/state/combat_state.py

"""
Combat tracking for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CombatState:
    """
    The attack currently in progress, if any.

    An attack in Four Souls is not one action but a series of rounds, and
    abilities may resolve between them. The engine therefore has to remember
    who is fighting whom across several stack resolutions, and that memory
    belongs to GameState so that saving mid-combat restores mid-combat.
    """

    attacker: int | None = None

    monster: Any | None = None

    round_number: int = 0

    settled_roll: int | None = None
    """
    The attack roll the table has finished answering, waiting to be applied.
    """

    active: bool = False

    stalled_rounds: int = 0
    """
    Rounds in a row in which neither side's hit points moved.

    An attack ends when somebody dies, so an attack in which nobody can be hurt
    would never end. Counting the rounds that changed nothing is how the engine
    notices, and it is a safeguard rather than a rule of the game: no card
    describes it, and content that deals damage never reaches it.
    """

    def begin(self, attacker: int, monster: Any) -> None:
        """
        Start an attack.
        """
        self.attacker = attacker
        self.monster = monster
        self.round_number = 0
        self.stalled_rounds = 0
        self.active = True

    def next_round(self) -> int:
        """
        Advance to the next combat round.
        """
        self.round_number += 1

        return self.round_number

    def end(self) -> None:
        """
        Finish the attack.
        """
        self.attacker = None
        self.monster = None
        self.round_number = 0
        self.stalled_rounds = 0
        self.active = False
