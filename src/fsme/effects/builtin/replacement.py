# src/fsme/effects/builtin/replacement.py

"""
Effects that edit an event instead of changing the game.

These only make sense inside a replacement ability, where the engine has
offered an event for editing before it happens. Outside that window there is
nothing to edit, and they say so rather than silently doing nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def _open_event(ctx: EffectContext, effect: str) -> Any:
    event = ctx.event

    if event is None:
        raise EffectExecutionError(
            f"'{effect}' may only be used by a replacement ability"
        )

    return event


def prevent_damage(
    ctx: EffectContext,
    targets: Sequence[Any],
    amount: int = 1,
) -> int:
    """
    Reduce the damage an event is about to deal.

    Preventing everything cancels the event outright, so nothing is recorded
    as having dealt zero damage.
    """
    if amount < 0:
        raise EffectExecutionError("prevent_damage amount must be non-negative")

    event = _open_event(ctx, "prevent_damage")

    before = int(event.get("amount", 0))
    after = max(0, before - amount)

    event.set("amount", after)

    if after == 0:
        event.cancel()

    return before - after


def cancel_event(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> bool:
    """
    Stop the event from happening at all.
    """
    _open_event(ctx, "cancel_event").cancel()

    return True


def modify_event(
    ctx: EffectContext,
    targets: Sequence[Any],
    key: str = "",
    value: Any = None,
    delta: int | None = None,
) -> Any:
    """
    Change one value carried by the event.

    ``delta`` shifts a number, ``value`` replaces it outright.
    """
    if not key:
        raise EffectExecutionError("modify_event requires a key")

    event = _open_event(ctx, "modify_event")

    if delta is not None:
        event.set(key, int(event.get(key, 0)) + int(delta))
    else:
        event.set(key, value)

    return event.get(key)


def register(registry: EffectRegistry) -> None:
    """
    Register every replacement effect.
    """
    registry.register(
        "prevent_damage",
        prevent_damage,
        primary="amount",
        description="Reduce incoming damage before it lands.",
    )
    registry.register(
        "cancel_event",
        cancel_event,
        description="Stop the event being replaced from happening.",
    )
    registry.register(
        "modify_event",
        modify_event,
        primary="key",
        description="Change a value carried by the event being replaced.",
    )
