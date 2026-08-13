# src/fsme/effects/builtin/copying.py

"""
Copying effects.

Copying is cheap in this engine because a card's behaviour is data. A copy is
the same immutable definition pointed at again, so nothing has to be cloned and
a copy cannot drift from what it copied.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.events import EventType
from fsme.stack import StackItem, StackItemType

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def copy_effect(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Put another copy of the top stack object on the stack.

    The copy is controlled by whoever copied it, which is the whole point: the
    same ability resolves twice, and the second time it answers to somebody
    else.
    """
    state = ctx.state

    items = list(targets) or (
        [] if state.stack.is_empty() else [state.stack.peek()]
    )

    copied = 0

    for item in items:
        if not isinstance(item, StackItem):
            raise EffectExecutionError("copy_effect expects stack objects")

        if item.ability is None:
            continue

        ctx.push(
            StackItem(
                kind=item.kind,
                label=f"{item.label}:copy",
                source=item.source,
                ability=item.ability,
                controller=ctx.actor if ctx.actor is not None else item.controller,
                targets=list(item.targets),
                event=item.event,
            )
        )

        copied += 1

    return copied


def copy_ability(
    ctx: EffectContext,
    targets: Sequence[Any],
    trigger: str = str(EventType.ON_ACTIVATE),
) -> int:
    """
    Use another card's ability without owning the card.
    """
    copied = 0

    for card in targets:
        definition = getattr(card, "definition", None)

        if definition is None:
            raise EffectExecutionError("copy_ability expects card targets")

        for ability in definition.abilities_for(trigger):
            ctx.push(
                StackItem(
                    kind=StackItemType.ACTIVATED_ABILITY,
                    label=f"{definition.id}:{ability.trigger}:copy",
                    source=card,
                    ability=ability,
                    controller=ctx.actor,
                )
            )

            copied += 1

    return copied


def duplicate(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Put a second copy of a card into play under the copier's control.

    The copy shares the original's definition and gets an identifier of its
    own, so the two are the same card and different objects — which is exactly
    what a duplicate is.
    """
    state = ctx.state
    owner = ctx.actor

    if owner is None or not 0 <= owner < len(state.players):
        return 0

    made = 0

    for card in targets:
        definition = getattr(card, "definition", None)

        if definition is None:
            raise EffectExecutionError("duplicate expects card targets")

        copy = type(card)(
            definition=definition,
            instance_id=state.ids.allocate("copy"),
            owner=owner,
            controller=owner,
        )

        state.player(owner).treasures.add_top(copy)
        made += 1

        ctx.emit(
            EventType.ON_ENTER,
            source=copy,
            controller=owner,
            copy_of=getattr(card, "instance_id", ""),
        )

    return made


def register(registry: EffectRegistry) -> None:
    """
    Register every copying effect.
    """
    registry.register(
        "copy_effect",
        copy_effect,
        description="Copy the ability currently on top of the stack.",
    )
    registry.register(
        "copy_ability",
        copy_ability,
        needs_target=True,
        primary="trigger",
        description="Use another card's ability.",
    )
    registry.register(
        "duplicate",
        duplicate,
        needs_target=True,
        description="Put a copy of a card into play.",
    )
