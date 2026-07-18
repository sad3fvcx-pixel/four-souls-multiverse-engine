# src/fsme/commands/types.py

"""
Core command types for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from enum import Enum, auto


class CommandType(Enum):
    """
    High-level engine command categories.
    """

    START_GAME = auto()
    END_GAME = auto()

    START_TURN = auto()
    END_TURN = auto()

    CHANGE_PHASE = auto()

    DRAW_CARD = auto()
    PLAY_CARD = auto()
    DISCARD_CARD = auto()

    PLAY_LOOT = auto()
    PLAY_TREASURE = auto()

    DECLARE_ATTACK = auto()
    RESOLVE_ATTACK = auto()

    DEAL_DAMAGE = auto()
    HEAL = auto()

    GAIN_COINS = auto()
    SPEND_COINS = auto()

    PUSH_STACK = auto()
    POP_STACK = auto()

    ACTIVATE_ITEM = auto()

    def __str__(self) -> str:
        return self.name.lower()