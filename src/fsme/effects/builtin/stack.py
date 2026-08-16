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

    Everything a player did and everything a card is doing can be taken off
    here — that is what "cancel everything that hasn't resolved" means. What
    cannot is the engine's own bookkeeping for an action already taken: see
    ``StackItem.cancellable``. Skipping those is not a special case for any
    card; it is the difference between undoing a thing and deleting the record
    of it.
    """
    state = ctx.state
    cancelled = 0

    for item in targets:
        if not isinstance(item, StackItem):
            raise EffectExecutionError("cancel_stack expects stack objects")

        if not item.cancellable:
            continue

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


def end_attack(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> bool:
    """
    Call off the attack in progress.

    "Cancel your attack if able" is not cancelling a card: the rounds still to
    come are the engine's own, and an attack that is already over cancels
    nothing.
    """
    from fsme.rules import end_combat

    state = ctx.state

    if not state.combat.active:
        return False

    for item in list(state.stack):
        if item.kind is StackItemType.COMBAT:
            state.stack.remove(item)
            item.cancel()

    end_combat(ctx)

    return True


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
        "end_attack",
        end_attack,
        description="Call off the attack in progress.",
    )
    registry.register(
        "end_turn",
        end_turn,
        description="End the current turn.",
    )
