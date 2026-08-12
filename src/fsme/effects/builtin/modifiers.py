# src/fsme/effects/builtin/modifiers.py

"""
Card state modifiers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.events import EventType

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def _cards(targets: Sequence[Any], effect: str) -> list[Any]:
    for target in targets:
        if not hasattr(target, "tapped"):
            raise EffectExecutionError(f"'{effect}' expects card targets")

    return list(targets)


def recharge(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Untap items so they may be activated again.
    """
    recharged = 0

    for card in _cards(targets, "recharge"):
        if not card.tapped:
            continue

        card.tapped = False
        recharged += 1

        ctx.emit(
            EventType.TREASURE_CHARGED,
            controller=card.controller,
            targets=[card],
        )

    return recharged


def deactivate(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Tap items so they may not be activated again this turn.
    """
    deactivated = 0

    for card in _cards(targets, "deactivate"):
        if card.tapped:
            continue

        card.tapped = True
        deactivated += 1

        ctx.emit(
            EventType.TREASURE_DEACTIVATED,
            controller=card.controller,
            targets=[card],
        )

    return deactivated


def add_counter(
    ctx: EffectContext,
    targets: Sequence[Any],
    counter: str = "",
    amount: int = 1,
) -> int:
    """
    Change a named counter on target cards.
    """
    if not counter:
        raise EffectExecutionError("add_counter requires a counter name")

    for card in _cards(targets, "add_counter"):
        card.counters[counter] = card.counters.get(counter, 0) + amount

    return amount


def register(registry: EffectRegistry) -> None:
    """
    Register every card modifier effect.
    """
    registry.register(
        "recharge", recharge, needs_target=True, description="Untap an item."
    )
    registry.register(
        "deactivate", deactivate, needs_target=True, description="Tap an item."
    )
    registry.register(
        "add_counter",
        add_counter,
        needs_target=True,
        primary="counter",
        description="Change a counter on a card.",
    )
