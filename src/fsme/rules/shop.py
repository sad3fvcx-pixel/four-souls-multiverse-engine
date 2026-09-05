# src/fsme/rules/shop.py

"""
Buying treasures.
"""

from __future__ import annotations

from typing import Any

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.effects.builtin.decks import draw_from
from fsme.events import EventType
from fsme.stack import PURCHASE, StackItem, StackItemType
from fsme.state import GamePhase, GameState, PlayerState
from fsme.state.modifiers import SHOP_COST

from .constants import TREASURE_COST
from .statics import bonus

DECK = "deck"
"""What a player buys when they buy the top of the treasure deck, unseen."""

SHOP = "shop"
"""What a player buys when they buy a card that is face up in a slot."""


class BuyTreasureHandler:
    """
    Buys a shop item, or the top card of the treasure deck, for the price.

    COMPREHENSIVE_RULES.md §6: both are the same purchase and cost the same,
    and a player gets one of them per turn. The difference is only that one
    card is face up and the other is not.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        if not state.started:
            return "the game has not started"

        if state.game_over:
            return "the game is over"

        if command.player != state.turn.active_player:
            return "only the active player may buy"

        if state.turn.phase is not GamePhase.ACTION:
            return f"treasures may not be bought during the {state.turn.phase} phase"

        player = state.player(command.player)

        if not player.alive:
            return "a dead player may not buy"

        if not player.can_buy():
            return "no purchases remaining this turn"

        price = shop_price(state, player.player_id)

        if player.pennies < price:
            return f"buying costs {price} cents, player has {player.pennies}"

        if command.get("source") == DECK:
            if not state.treasure_deck.cards:
                return "the treasure deck is empty"

            return None

        index = command.get("index", 0)

        if not isinstance(index, int) or not 0 <= index < len(state.treasure_shop):
            return f"no treasure on offer at index {index!r}"

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        """
        Declare the purchase and put the declaration in the queue.

        COMPREHENSIVE_RULES.md §6: buying is declared, and paying and taking
        the item happen when the declaration resolves. That is the whole reason
        a purchase can be answered — and the reason it can arrive at its own
        resolution to find the item gone.
        """
        state = context.state
        player = state.player(command.player)

        # The turn's purchase is spent by declaring it: a player cannot queue
        # two buys and see which one survives. A purchase that fizzles is given
        # back when it fizzles, which is what §12 means by "not spent".
        player.spend_purchase()

        context.emit(
            EventType.BEFORE_PURCHASE,
            controller=player.player_id,
            cost=shop_price(state, player.player_id),
        )

        context.push(
            StackItem(
                kind=StackItemType.ENGINE_EFFECT,
                label=PURCHASE,
                controller=player.player_id,
                payload={
                    "source": str(command.get("source", SHOP)),
                    "index": int(command.get("index", 0) or 0),
                },
            )
        )


def purchase(item: StackItem, context: EffectContext) -> None:
    """
    Carry out a declared purchase, or let it fizzle.

    COMPREHENSIVE_RULES.md §12: a purchase fizzles when the shop item it named
    has left its slot, or the buyer no longer has the money — and a purchase
    that fizzles is not spent, so the turn's buy is handed back.
    """
    state = context.state
    seat = item.controller

    if seat is None or not 0 <= seat < len(state.players):
        return

    player = state.player(seat)
    price = shop_price(state, seat)

    card = _what_was_bought(context, item)

    if card is None or player.pennies < price or not player.alive:
        _give_the_purchase_back(player)

        context.emit(
            EventType.PURCHASE_FIZZLED,
            controller=seat,
            targets=[player],
            cost=price,
        )

        return

    context.apply("lose_coins", [player], amount=price)

    card.owner = seat
    card.controller = seat
    card.zone = str(player.treasures.zone_type)

    player.treasures.add_top(card)

    refill_shop(context)

    context.emit(EventType.TREASURE_BOUGHT, source=card, controller=seat)
    context.emit(EventType.ON_ENTER, source=card, controller=seat)
    context.emit(EventType.AFTER_PURCHASE, source=card, controller=seat)


def _what_was_bought(context: EffectContext, item: StackItem) -> Any | None:
    """
    Take the declared card out of the shop or off the deck, if it is still there.
    """
    state = context.state

    if str(item.payload.get("source", SHOP)) == DECK:
        drawn: Any | None = draw_from(context, "treasure")

        return drawn

    index = int(item.payload.get("index", 0))

    if not 0 <= index < len(state.treasure_shop):
        return None

    bought: Any = state.treasure_shop.cards.pop(index)

    return bought


def _give_the_purchase_back(player: PlayerState) -> None:
    """
    Return the turn's buy to a player whose purchase came to nothing.
    """
    player.purchases_left += 1


def shop_price(state: GameState, player_id: int) -> int:
    """
    What this player pays for a shop item right now.

    The shop's price is printed in the rules; cards move it, and a card that
    makes shopping cheaper cannot take it below nothing.
    """
    return max(0, TREASURE_COST + bonus(state, SHOP_COST, player_id))


def refill_shop(context: EffectContext) -> None:
    """
    Top the shop back up from the treasure deck.
    """
    state = context.state

    while len(state.treasure_shop) < state.shop_slots:
        card = draw_from(context, "treasure")

        if card is None:
            break

        state.treasure_shop.add_top(card)
