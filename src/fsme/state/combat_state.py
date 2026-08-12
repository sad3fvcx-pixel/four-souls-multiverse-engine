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

    active: bool = False

    def begin(self, attacker: int, monster: Any) -> None:
        """
        Start an attack.
        """
        self.attacker = attacker
        self.monster = monster
        self.round_number = 0
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
        self.active = False
