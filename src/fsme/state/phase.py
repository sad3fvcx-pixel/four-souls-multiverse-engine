# src/fsme/state/phase.py

"""
Game phase definitions for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from enum import Enum, auto


class GamePhase(Enum):
    """
    Main phases of a player's turn.

    The order follows the official Four Souls turn structure.
    """

    START = auto()
    LOOT = auto()
    ACTION = auto()
    END = auto()

    def __str__(self) -> str:
        return self.name.lower()

    @property
    def is_start(self) -> bool:
        return self is GamePhase.START

    @property
    def is_loot(self) -> bool:
        return self is GamePhase.LOOT

    @property
    def is_action(self) -> bool:
        return self is GamePhase.ACTION

    @property
    def is_end(self) -> bool:
        return self is GamePhase.END

    @property
    def is_main_phase(self) -> bool:
        """
        Returns True if players may freely use loot cards,
        activate abilities and attack.
        """
        return self is GamePhase.ACTION