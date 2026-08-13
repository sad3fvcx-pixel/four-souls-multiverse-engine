# src/fsme/effects/builtin/stack.py

"""
Effects that act on the stack itself.

Cancelling is the one thing a card does to another card's ability rather than
to the board. The cancelled object is taken off the stack and never resolves;
it is not "resolved with no effect", because a card that reacts to something
resolving must not react to something that did not.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.events import EventType
from fsme.stack import ADVANCE_TURN, StackItem, StackItemType

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def cancel_stack(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Take stack objects off the stack without resolving them.
    """
    state = ctx.state
    cancelled = 0

    for item in targets:
        if not isinstance(item, StackItem):
            raise EffectExecutionError("cancel_stack expects stack objects")

        if not state.stack.remove(item):
            continue

        item.cancel()
        cancelled += 1

        ctx.emit(
            EventType.STACK_CANCEL,
            source=item.source,
            controller=item.controller,
            label=item.label,
        )

    return cancelled


def end_turn(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    End the current turn from inside an ability.

    The turn ends the way it always ends — the engine's own turn-advancing
    object goes on the stack — so everything that happens at the end of a turn
    still happens. A card ending the turn is not a second way to end one.
    """
    controller = ctx.actor

    if controller is None:
        controller = ctx.state.turn.active_player

    ctx.push(
        StackItem(
            kind=StackItemType.ENGINE_EFFECT,
            label=ADVANCE_TURN,
            controller=int(controller),
        )
    )

    return 1


def register(registry: EffectRegistry) -> None:
    """
    Register every stack effect.
    """
    registry.register(
        "cancel_stack",
        cancel_stack,
        needs_target=True,
        description="Cancel an ability or card waiting on the stack.",
    )
    registry.register(
        "end_turn",
        end_turn,
        description="End the current turn.",
    )
