# src/fsme/rules/loot.py

"""
Playing loot cards.
"""

from __future__ import annotations

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.events import EventType
from fsme.stack import StackItem, StackItemType
from fsme.state import GamePhase, GameState

from .constants import LOOT_PLAYS_PER_TURN
from .statics import cards_in_play

DISCARD_PLAYED_LOOT = "discard_played_loot"


class PlayLootHandler:
    """
    Plays one loot card from the active player's hand.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        if not state.started:
            return "the game has not started"

        if state.game_over:
            return "the game is over"

        if command.player != state.turn.active_player:
            return "only the active player may play loot"

        player = state.player(command.player)

        if not player.alive:
            return "a dead player may not play loot"

        if state.turn.phase not in (GamePhase.LOOT, GamePhase.ACTION):
            return f"loot may not be played during the {state.turn.phase} phase"

        allowance = LOOT_PLAYS_PER_TURN + player.additional_loot_plays

        if state.turn.loot_played >= allowance:
            return "no loot plays remaining this turn"

        index = command.get("index", 0)

        if not isinstance(index, int) or not 0 <= index < player.hand_size:
            return f"no loot card at hand index {index!r}"

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state
        player = state.player(command.player)

        card = player.hand.cards.pop(int(command.get("index", 0)))

        state.turn.record_loot_play()

        context.emit(
            EventType.BEFORE_LOOT,
            source=card,
            controller=player.player_id,
        )

        # Pushed before the card's own ability, so it resolves after it: the
        # loot card reaches the discard pile only once its effect is done.
        context.push(
            StackItem(
                kind=StackItemType.LOOT,
                label=DISCARD_PLAYED_LOOT,
                source=card,
                controller=player.player_id,
            )
        )

        context.emit(
            EventType.ON_PLAY,
            source=card,
            controller=player.player_id,
        )


def discard_played_loot(item: StackItem, context: EffectContext) -> None:
    """
    Move a resolved loot card to the discard pile.

    A card that put itself into play — a curse attaching to a player — stays
    where it went. Discarding it as well would leave the same card in two
    places at once.
    """
    card = item.source

    if card is None:
        return

    if card in cards_in_play(context.state):
        return

    context.state.loot_discard.add_top(card)

    context.emit(
        EventType.AFTER_LOOT,
        source=card,
        controller=item.controller,
    )
