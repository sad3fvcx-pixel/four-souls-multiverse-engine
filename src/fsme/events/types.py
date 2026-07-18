# src/fsme/events/types.py

"""
Core event types for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from enum import Enum, auto


class EventType(Enum):
    """
    High-level event categories emitted by the engine.
    """

    TURN_STARTED = auto()
    TURN_ENDED = auto()

    PHASE_CHANGED = auto()

    CARD_DRAWN = auto()
    CARD_PLAYED = auto()
    CARD_DISCARDED = auto()

    ATTACK_DECLARED = auto()
    ATTACK_RESOLVED = auto()

    DAMAGE_DEALT = auto()
    HEAL_RECEIVED = auto()

    PLAYER_DIED = auto()
    PLAYER_REVIVED = auto()

    COINS_GAINED = auto()
    COINS_SPENT = auto()

    STACK_PUSHED = auto()
    STACK_POPPED = auto()

    EFFECT_RESOLVED = auto()

    GAME_STARTED = auto()
    GAME_ENDED = auto()

    def __str__(self) -> str:
        return self.name.lower()