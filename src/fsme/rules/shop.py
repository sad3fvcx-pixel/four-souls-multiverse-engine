# src/fsme/rules/shop.py

"""
Buying treasures.
"""

from __future__ import annotations

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.events import EventType
from fsme.state import GamePhase, GameState
from fsme.state.modifiers import SHOP_COST

from .constants import TREASURE_COST
from .statics import bonus

DECK = "deck"
"""What a player buys when they buy the top of the treasure deck, unseen."""


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
        state = context.state
        player = state.player(command.player)

        price = shop_price(state, player.player_id)

        player.spend_purchase()

        context.emit(
            EventType.BEFORE_PURCHASE,
            controller=player.player_id,
            cost=price,
        )

        context.apply("lose_coins", [player], amount=price)

        if command.get("source") == DECK:
            card = state.treasure_deck.draw()
        else:
            card = state.treasure_shop.cards.pop(int(command.get("index", 0)))

        card.owner = player.player_id
        card.controller = player.player_id
        card.zone = str(player.treasures.zone_type)

        player.treasures.add_top(card)

        refill_shop(context)

        context.emit(
            EventType.TREASURE_BOUGHT,
            source=card,
            controller=player.player_id,
        )
        context.emit(
            EventType.ON_ENTER,
            source=card,
            controller=player.player_id,
        )
        context.emit(
            EventType.AFTER_PURCHASE,
            source=card,
            controller=player.player_id,
        )


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

    while len(state.treasure_shop) < state.shop_slots and state.treasure_deck.cards:
        state.treasure_shop.add_top(state.treasure_deck.draw())
