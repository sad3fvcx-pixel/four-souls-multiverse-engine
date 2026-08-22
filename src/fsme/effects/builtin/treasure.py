# src/fsme/effects/builtin/treasure.py

"""
Treasure effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.content.vocabulary import WHOM
from fsme.events import EventType
from fsme.state import PlayerState

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry
from .decks import draw_from


def gain_treasure(ctx: EffectContext, targets: Sequence[Any], count: int = 1) -> int:
    """
    Give each target player the top treasures of the deck.
    """
    if count < 0:
        raise EffectExecutionError("gain_treasure count must be non-negative")

    gained = 0

    for player in targets:
        if not isinstance(player, PlayerState):
            raise EffectExecutionError("gain_treasure expects player targets")

        for _ in range(count):
            card = draw_from(ctx, "treasure")

            if card is None:
                break

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


def put_into_play(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Put cards into their controller's play area as items.

    A trinket is a loot card that says it becomes an item when it resolves, so
    the card being resolved is usually its own target. It is on the stack and in
    no zone at that moment, which is why nothing has to be taken out of one
    first — and why the rule that discards a played loot card leaves alone
    anything that has put itself somewhere.
    """
    state = ctx.state
    owner = ctx.actor

    if owner is None or not 0 <= owner < len(state.players):
        return 0

    player = state.player(owner)
    entered = 0

    for card in targets:
        _detach(state, card)

        card.owner = owner
        card.controller = owner

        player.treasures.add_top(card)
        entered += 1

        ctx.emit(
            EventType.ON_GAIN,
            source=card,
            controller=owner,
            targets=[player],
        )
        ctx.emit(
            EventType.ON_ENTER,
            source=card,
            controller=owner,
        )

    return entered


def _detach(state: Any, card: Any) -> None:
    """
    Take a card out of whichever zone holds it, if any holds it at all.
    """
    zones = [state.loot_deck, state.loot_discard, state.treasure_deck]

    for player in state.players:
        zones.append(player.hand)

    for zone in zones:
        if card in zone.cards:
            zone.cards.remove(card)
            return


def _is_eternal(card: Any) -> bool:
    return bool(getattr(card, "is_eternal", False))


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

    Destruction is offered for replacement first, because a card can answer it:
    "if this would be destroyed, it becomes a soul instead" is not a reaction to
    having been destroyed — it is the destruction not happening.
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

        proposal = ctx.propose(
            EventType.BEFORE_DESTROY,
            source=card,
            controller=owner,
            targets=[card],
        )

        if proposal.cancelled:
            continue

        if card not in treasures.cards:
            # A replacement took the card somewhere else — into the soul pile,
            # for one — and there is nothing left here to destroy.
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

        if holder is None:
            # An item in the shop belongs to nobody, and a card that offers it
            # alongside the players' items means taking it rather than buying
            # it. The shop is left one short until the rules refill it.
            if card not in state.treasure_shop.cards:
                continue

            state.treasure_shop.cards.remove(card)
        elif holder.player_id == thief_id:
            continue
        else:
            holder.treasures.cards.remove(card)

        card.controller = thief_id
        card.tapped = True

        thief.treasures.add_top(card)
        stolen += 1

        ctx.emit(
            EventType.TREASURE_STOLEN,
            source=card,
            controller=thief_id,
            targets=[holder] if holder is not None else [],
            stolen_from=holder.player_id if holder is not None else None,
        )

    return stolen


def give_treasure(ctx: EffectContext, targets: Sequence[Any], to: Any = None) -> int:
    """
    Hand items to another player.

    Giving is not stealing: the item is offered, so ownership follows control
    the way it does when a card changes hands willingly.

    Nobody to give to is not an error. "Give an item to another player" in a
    two-player game whose other player is dead names nobody, and the rules pass
    over an instruction that cannot be carried out — which is what every other
    effect here does when its recipient turns out not to exist.
    """
    state = ctx.state

    if to is None or not 0 <= int(to) < len(state.players):
        return 0

    receiver = state.player(int(to))
    given = 0

    for card in targets:
        if _is_eternal(card):
            continue

        holder = _holder(state, card)

        if holder is None or holder.player_id == receiver.player_id:
            continue

        holder.treasures.cards.remove(card)

        card.owner = receiver.player_id
        card.controller = receiver.player_id

        receiver.treasures.add_top(card)
        given += 1

        ctx.emit(
            EventType.ON_GAIN,
            source=card,
            controller=receiver.player_id,
            targets=[receiver],
        )

    return given


def swap_cards(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Exchange two cards between the players holding them.

    Exactly two: a swap with one card is a gift and a swap with three is not a
    swap, so anything else does nothing at all. The cards keep everything about
    themselves except whose they are.
    """
    if len(targets) != 2:
        # Two cards make a swap, and when the board could only offer one there
        # is nothing to exchange. The card is passed over, as the rules pass
        # over an instruction that cannot be carried out.
        return 0

    state = ctx.state
    first, second = targets

    if first is second:
        # One card named twice. Exchanging it with itself would move it to
        # where it already is, and the instruction is passed over for the same
        # reason a swap with one card is.
        return 0

    left = _zone_of(state, first)
    right = _zone_of(state, second)

    if left is None or right is None:
        return 0

    left_zone, left_owner = left
    right_zone, right_owner = right

    left_zone.cards.remove(first)
    right_zone.cards.remove(second)

    left_zone.add_top(second)
    right_zone.add_top(first)

    for card, owner in ((second, left_owner), (first, right_owner)):
        card.owner = owner
        card.controller = owner

    ctx.emit(
        EventType.ON_GAIN,
        source=second,
        controller=left_owner,
        targets=[state.player(left_owner)],
    )
    ctx.emit(
        EventType.ON_GAIN,
        source=first,
        controller=right_owner,
        targets=[state.player(right_owner)],
    )

    return 2


def _zone_of(state: Any, card: Any) -> tuple[Any, int] | None:
    """
    Find the hand or play area holding a card, and whose it is.
    """
    for player in state.players:
        for zone in (player.treasures, player.hand):
            if card in zone.cards:
                return zone, player.player_id

    return None


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
        asks={
            "count": "how many items",
        },
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
    registry.register(
        "give_treasure",
        give_treasure,
        needs_target=True,
        primary="to",
        description="Hand an item to another player.",
        roles={"to": WHOM},
    )
    registry.register(
        "swap_cards",
        swap_cards,
        needs_target=True,
        description="Exchange two cards between their holders.",
    )
    registry.register(
        "put_into_play",
        put_into_play,
        needs_target=True,
        description="Put a card into play as an item under your control.",
    )
