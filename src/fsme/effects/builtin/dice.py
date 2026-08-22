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
from fsme.runtime.errors import RollRequired
from fsme.state.modifiers import ROLL

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def rolled(ctx: EffectContext, sides: int = 6, attack: bool = False) -> int:
    """
    Roll a die and let anything that changes rolls have its say.

    The natural result is offered for replacement before it counts, so a card
    that adds one to a roll works the same whether the roll came from an
    ability or from an attack. The final value is kept on the die's own face:
    a six-sided die cannot show a seven, however much is added to it.

    When the game is being played with priority windows, the roll does not
    return here at all: the table has to be given the chance to answer it, and
    that means parking whatever was rolling. The Runtime does the parking; this
    function only says that it is needed, and returns the settled result when
    the ability comes back to the same operation.
    """
    if sides < 1:
        raise EffectExecutionError("a die must have at least one side")

    settled = ctx.take_settled_roll()

    if settled is not None:
        return int(settled)

    if ctx.answerable_rolls:
        raise RollRequired(sides, attack=attack)

    return natural_roll(ctx, sides, attack=attack)


def natural_roll(ctx: EffectContext, sides: int, *, attack: bool = False) -> int:
    """
    Roll the die and apply everything that changes a roll without being asked.
    """
    natural = ctx.roll(sides)

    proposal = ctx.propose(
        EventType.ROLL_MODIFIED,
        controller=ctx.actor,
        sides=sides,
        value=natural + _roll_bonus(ctx),
        natural=natural,
        attack=attack,
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
    ctx.emit(EventType.BEFORE_ROLL, controller=ctx.actor, sides=sides)

    value = rolled(ctx, sides)

    ctx.emit(EventType.AFTER_ROLL, controller=ctx.actor, sides=sides, value=value)

    return value


def reroll(ctx: EffectContext, targets: Sequence[Any], sides: int = 6) -> int:
    """
    Roll again, replacing a previous result.

    A roll the table is answering is rerolled where it lies: it has not
    happened yet, so there is nothing to announce and nothing to resume.
    """
    waiting = ctx.state.pending_roll

    if waiting is not None:
        value = waiting.settle(natural_roll(ctx, waiting.sides, attack=waiting.attack))

        ctx.emit(EventType.REROLL, sides=waiting.sides, value=value)

        return value

    value = natural_roll(ctx, sides)

    ctx.emit(EventType.REROLL, sides=sides, value=value)
    ctx.emit(EventType.AFTER_ROLL, sides=sides, value=value)

    return value


def modify_roll(ctx: EffectContext, targets: Sequence[Any], amount: int = 0) -> int:
    """
    Shift a roll: the one being replaced, or the one the table is answering.

    With no roll anywhere there is nothing to shift, and a card played at the
    wrong moment does nothing rather than breaking the game. Whether it was
    worth playing is the player's business.
    """
    waiting = ctx.state.pending_roll

    if waiting is not None:
        return waiting.settle(waiting.value + int(amount))

    event = ctx.event

    if event is None:
        return 0

    value = int(event.get("value", 0)) + int(amount)

    event.set("value", value)

    return value


def set_roll(ctx: EffectContext, targets: Sequence[Any], value: int = 1) -> int:
    """
    Change a roll to a chosen number.

    A die cannot show a number it does not have, so the result is kept on its
    face however the card is written. With no roll open there is nothing to
    change, and the card does nothing.
    """
    waiting = ctx.state.pending_roll

    if waiting is not None:
        return waiting.settle(int(value))

    event = ctx.event

    if event is None:
        return 0

    sides = int(event.get("sides", 6))
    kept = max(1, min(sides, int(value)))

    event.set("value", kept)

    return kept


def flip_roll(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Turn a roll over: a one becomes a six, a two a five.

    The die is not rolled again. It is read from the other side, which is why
    the result is one more than the number of faces less what it showed.
    """
    waiting = ctx.state.pending_roll

    if waiting is not None:
        return waiting.settle(waiting.sides + 1 - waiting.value)

    event = ctx.event

    if event is None:
        return 0

    sides = int(event.get("sides", 6))
    flipped = max(1, min(sides, sides + 1 - int(event.get("value", 1))))

    event.set("value", flipped)

    return flipped


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
        asks={
            "sides": "how many sides the die has",
        },
    )
    registry.register(
        "reroll",
        reroll,
        primary="sides",
        stores="dice",
        description="Roll a die again, replacing the stored result.",
        asks={
            "sides": "how many sides the die has",
        },
    )
    registry.register(
        "set_roll",
        set_roll,
        primary="value",
        description="Change an open roll to a chosen number.",
        asks={
            "value": "what the die now shows",
        },
    )
    registry.register(
        "flip_roll",
        flip_roll,
        description="Read an open roll from the other side of the die.",
    )
    registry.register(
        "modify_roll",
        modify_roll,
        primary="amount",
        description="Change a roll while it is being modified.",
        asks={
            "amount": "how much to change the roll by",
        },
    )
