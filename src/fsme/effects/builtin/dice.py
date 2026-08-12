# src/fsme/effects/builtin/dice.py

"""
Dice effects.

Every roll goes through the engine RNG. RNG.md forbids any other source of
randomness, and it also forbids unnecessary calls: one roll effect consumes
exactly one RNG value, so replaying the same commands reproduces the same dice.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.events import EventType

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def roll_dice(ctx: EffectContext, targets: Sequence[Any], sides: int = 6) -> int:
    """
    Roll a die and announce the result.
    """
    if sides < 1:
        raise EffectExecutionError("roll_dice sides must be positive")

    ctx.emit(EventType.BEFORE_ROLL, sides=sides)

    value = ctx.roll(sides)

    ctx.emit(EventType.AFTER_ROLL, sides=sides, value=value)

    return value


def reroll(ctx: EffectContext, targets: Sequence[Any], sides: int = 6) -> int:
    """
    Roll again, replacing a previous result.
    """
    if sides < 1:
        raise EffectExecutionError("reroll sides must be positive")

    value = ctx.roll(sides)

    ctx.emit(EventType.REROLL, sides=sides, value=value)
    ctx.emit(EventType.AFTER_ROLL, sides=sides, value=value)

    return value


def register(registry: EffectRegistry) -> None:
    """
    Register every dice effect.
    """
    registry.register(
        "roll_dice",
        roll_dice,
        primary="sides",
        stores="dice",
        description="Roll a die through the engine RNG.",
    )
    registry.register(
        "reroll",
        reroll,
        primary="sides",
        stores="dice",
        description="Roll a die again, replacing the stored result.",
    )
