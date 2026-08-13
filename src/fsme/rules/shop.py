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


class BuyTreasureHandler:
    """
    Buys the chosen shop item for the official price.
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

        price = shop_price(state, player.player_id)

        if player.pennies < price:
            return f"buying costs {price} cents, player has {player.pennies}"

        index = command.get("index", 0)

        if not isinstance(index, int) or not 0 <= index < len(state.treasure_shop):
            return f"no treasure on offer at index {index!r}"

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state
        player = state.player(command.player)

        price = shop_price(state, player.player_id)

        context.emit(
            EventType.BEFORE_PURCHASE,
            controller=player.player_id,
            cost=price,
        )

        context.apply("lose_coins", [player], amount=price)

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
