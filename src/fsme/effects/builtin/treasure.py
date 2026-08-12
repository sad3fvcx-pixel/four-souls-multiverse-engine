# src/fsme/effects/builtin/treasure.py

"""
Treasure effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.events import EventType
from fsme.state import PlayerState

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def gain_treasure(ctx: EffectContext, targets: Sequence[Any], count: int = 1) -> int:
    """
    Give each target player the top treasures of the deck.
    """
    if count < 0:
        raise EffectExecutionError("gain_treasure count must be non-negative")

    state = ctx.state
    gained = 0

    for player in targets:
        if not isinstance(player, PlayerState):
            raise EffectExecutionError("gain_treasure expects player targets")

        for _ in range(count):
            if not state.treasure_deck.cards:
                break

            card = state.treasure_deck.draw()

            card.owner = player.player_id
            card.controller = player.player_id

            player.treasures.add_top(card)
            gained += 1

            ctx.emit(
                EventType.ON_GAIN,
                source=card,
                controller=player.player_id,
                targets=[player],
            )
            ctx.emit(
                EventType.ON_ENTER,
                source=card,
                controller=player.player_id,
            )

    return gained


def destroy_treasure(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Send target items to the treasure discard pile.
    """
    state = ctx.state
    destroyed = 0

    for card in targets:
        owner = getattr(card, "owner", None)

        if owner is None or not 0 <= owner < len(state.players):
            continue

        treasures = state.player(owner).treasures

        if card not in treasures.cards:
            continue

        treasures.cards.remove(card)
        state.treasure_discard.add_top(card)
        destroyed += 1

        ctx.emit(
            EventType.TREASURE_DESTROYED,
            source=card,
            controller=owner,
        )
        ctx.emit(
            EventType.ON_DESTROY,
            source=card,
            controller=owner,
        )

    return destroyed


def register(registry: EffectRegistry) -> None:
    """
    Register every treasure effect.
    """
    registry.register(
        "gain_treasure",
        gain_treasure,
        needs_target=True,
        primary="count",
        description="Take treasures from the top of the deck.",
    )
    registry.register(
        "destroy_treasure",
        destroy_treasure,
        needs_target=True,
        description="Destroy an item.",
    )
