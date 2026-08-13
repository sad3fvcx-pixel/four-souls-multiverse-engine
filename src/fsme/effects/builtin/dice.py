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
from fsme.state.modifiers import ROLL

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def rolled(ctx: EffectContext, sides: int = 6) -> int:
    """
    Roll a die and let anything that changes rolls have its say.

    The natural result is offered for replacement before it counts, so a card
    that adds one to a roll works the same whether the roll came from an
    ability or from an attack. The final value is kept on the die's own face:
    a six-sided die cannot show a seven, however much is added to it.
    """
    if sides < 1:
        raise EffectExecutionError("a die must have at least one side")

    natural = ctx.roll(sides)

    proposal = ctx.propose(
        EventType.ROLL_MODIFIED,
        sides=sides,
        value=natural + _roll_bonus(ctx),
        natural=natural,
    )

    if proposal.cancelled:
        return natural

    return max(1, min(sides, int(proposal.get("value", natural))))


def _roll_bonus(ctx: EffectContext) -> int:
    """
    What the roller adds to the die before anybody replaces the result.

    A card that says "+1 to your dice rolls" is not a replacement ability
    waiting for a window; it is a number the roller simply has. Offering the
    already-adjusted value for replacement keeps the two kinds in the right
    order: a bonus applies, and then anything that edits rolls edits the roll
    the player actually made.
    """
    roller = ctx.actor

    if roller is None or not 0 <= roller < len(ctx.state.players):
        return 0

    total = 0

    for modifier in ctx.state.modifiers:
        if modifier.stat == ROLL and modifier.player_id == roller:
            total += modifier.amount

    return total


def roll_dice(ctx: EffectContext, targets: Sequence[Any], sides: int = 6) -> int:
    """
    Roll a die and announce the result.
    """
    ctx.emit(EventType.BEFORE_ROLL, sides=sides)

    value = rolled(ctx, sides)

    ctx.emit(EventType.AFTER_ROLL, sides=sides, value=value)

    return value


def reroll(ctx: EffectContext, targets: Sequence[Any], sides: int = 6) -> int:
    """
    Roll again, replacing a previous result.
    """
    value = rolled(ctx, sides)

    ctx.emit(EventType.REROLL, sides=sides, value=value)
    ctx.emit(EventType.AFTER_ROLL, sides=sides, value=value)

    return value


def modify_roll(ctx: EffectContext, targets: Sequence[Any], amount: int = 0) -> int:
    """
    Shift the roll currently being offered for modification.
    """
    event = ctx.event

    if event is None:
        raise EffectExecutionError(
            "'modify_roll' may only be used while a roll is being modified"
        )

    value = int(event.get("value", 0)) + int(amount)

    event.set("value", value)

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
    registry.register(
        "modify_roll",
        modify_roll,
        primary="amount",
        description="Change a roll while it is being modified.",
    )
