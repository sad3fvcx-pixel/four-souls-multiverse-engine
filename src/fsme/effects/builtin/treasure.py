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


def _is_eternal(card: Any) -> bool:
    definition = getattr(card, "definition", None)

    return bool(getattr(definition, "is_eternal", False))


def _holder(state: Any, card: Any) -> Any | None:
    """
    Find the player currently holding an item.

    Control matters here, not ownership: a stolen item is destroyed out of the
    hands of whoever has it.
    """
    for player in state.players:
        if card in player.treasures.cards:
            return player

    return None


def destroy_treasure(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Send target items to the treasure discard pile.

    An eternal item cannot be destroyed and is passed over in silence, the way
    the rules pass over an instruction that cannot be carried out.
    """
    state = ctx.state
    destroyed = 0

    for card in targets:
        if _is_eternal(card):
            continue

        holder = _holder(state, card)

        if holder is None:
            continue

        treasures = holder.treasures
        owner = holder.player_id

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


def steal_treasure(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Take target items for the player doing the stealing.

    Ownership does not change, only control. A card that returns an item to its
    owner needs to know who that was, and a thief does not become one.
    """
    state = ctx.state
    thief_id = ctx.actor

    if thief_id is None or not 0 <= thief_id < len(state.players):
        return 0

    thief = state.player(thief_id)
    stolen = 0

    for card in targets:
        if _is_eternal(card):
            continue

        holder = _holder(state, card)

        if holder is None or holder.player_id == thief_id:
            continue

        holder.treasures.cards.remove(card)

        card.controller = thief_id
        card.tapped = True

        thief.treasures.add_top(card)
        stolen += 1

        ctx.emit(
            EventType.TREASURE_STOLEN,
            source=card,
            controller=thief_id,
            targets=[holder],
            stolen_from=holder.player_id,
        )

    return stolen


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
    registry.register(
        "steal_treasure",
        steal_treasure,
        needs_target=True,
        description="Take an item from another player.",
    )
