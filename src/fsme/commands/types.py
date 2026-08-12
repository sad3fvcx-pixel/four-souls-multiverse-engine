# src/fsme/commands/types.py

"""
Command vocabulary for Four Souls Multiverse Engine.

A command is an intent, never a result. "Deal damage" is not a command: it is
what happens after ``attack`` is validated and resolved. Keeping results out of
this list is what stops external systems from reaching past validation.
"""

from __future__ import annotations

from enum import StrEnum


class CommandType(StrEnum):
    """
    Every action an external actor may request.
    """

    START_GAME = "start_game"

    PLAY_LOOT = "play_loot"
    ACTIVATE_TREASURE = "activate_treasure"
    ATTACK = "attack"
    BUY_TREASURE = "buy_treasure"
    END_PHASE = "end_phase"
    END_TURN = "end_turn"

    CHOOSE_TARGET = "choose_target"
    PASS_PRIORITY = "pass_priority"
