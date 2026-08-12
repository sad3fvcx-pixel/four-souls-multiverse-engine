# src/fsme/rules/shop.py

"""
Buying treasures.
"""

from __future__ import annotations

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.events import EventType
from fsme.state import GamePhase, GameState

from .constants import SHOP_SLOTS, TREASURE_COST


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

        if player.pennies < TREASURE_COST:
            return f"buying costs {TREASURE_COST} cents, player has {player.pennies}"

        index = command.get("index", 0)

        if not isinstance(index, int) or not 0 <= index < len(state.treasure_shop):
            return f"no treasure on offer at index {index!r}"

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state
        player = state.player(command.player)

        context.emit(
            EventType.BEFORE_PURCHASE,
            controller=player.player_id,
            cost=TREASURE_COST,
        )

        context.apply("lose_coins", [player], amount=TREASURE_COST)

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


def refill_shop(context: EffectContext) -> None:
    """
    Top the shop back up from the treasure deck.
    """
    state = context.state

    while len(state.treasure_shop) < SHOP_SLOTS and state.treasure_deck.cards:
        state.treasure_shop.add_top(state.treasure_deck.draw())
