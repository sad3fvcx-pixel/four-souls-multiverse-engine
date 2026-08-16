# src/fsme/rules/loot.py

"""
Playing loot cards.
"""

from __future__ import annotations

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.events import EventType
from fsme.stack import DISCARD_PLAYED_LOOT, StackItem, StackItemType
from fsme.state import GamePhase, GameState

from .constants import LOOT_PLAYS_PER_TURN
from .restrictions import PLAY_LOOT, refuse
from .statics import cards_in_play


class PlayLootHandler:
    """
    Plays one loot card from the active player's hand.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        if not state.started:
            return "the game has not started"

        if state.game_over:
            return "the game is over"

        responding = state.priority.is_open and state.priority.holder == command.player

        if command.player != state.turn.active_player and not responding:
            return "only the active player may play loot"

        player = state.player(command.player)

        if not player.alive:
            return "a dead player may not play loot"

        # STACK.md section 9 counts playing a loot card among the things a
        # player may do while holding priority, so a player answering somebody
        # else's card is not bound by the phase — the phase belongs to the
        # player whose turn it is.
        if not responding and state.turn.phase not in (GamePhase.LOOT, GamePhase.ACTION):
            return f"loot may not be played during the {state.turn.phase} phase"

        allowance = LOOT_PLAYS_PER_TURN + player.additional_loot_plays

        if not player.loot_limit_lifted and player.loot_played >= allowance:
            return "no loot plays remaining this turn"

        index = command.get("index", 0)

        if not isinstance(index, int) or not 0 <= index < player.hand_size:
            return f"no loot card at hand index {index!r}"

        return refuse(state, PLAY_LOOT, player=command.player)

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state
        player = state.player(command.player)

        card = player.hand.cards.pop(int(command.get("index", 0)))

        state.turn.record_loot_play()
        player.loot_played += 1

        context.emit(
            EventType.BEFORE_LOOT,
            source=card,
            controller=player.player_id,
        )

        # Pushed before the card's own ability, so it resolves after it: the
        # loot card reaches the discard pile only once its effect is done.
        #
        # Not cancellable, because it is not a thing anybody did — it is the
        # tail of this very command, waiting its turn. The card has already
        # left the hand; cancelling only the part that puts it down leaves it
        # in no zone at all.
        context.push(
            StackItem(
                kind=StackItemType.LOOT,
                label=DISCARD_PLAYED_LOOT,
                source=card,
                controller=player.player_id,
                cancellable=False,
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

    A card that put itself somewhere stays there. A curse attaches to a player,
    a trinket becomes an item, Lost Soul becomes a soul and The Sun goes to the
    bottom of the loot deck; discarding any of them as well would leave the same
    card in two places at once. So the question is not "is it in play" but "is it
    anywhere", and only a card that is nowhere is discarded.
    """
    card = item.source

    if card is None:
        return

    if _is_anywhere(context.state, card):
        return

    context.state.loot_discard.add_top(card)

    context.emit(
        EventType.AFTER_LOOT,
        source=card,
        controller=item.controller,
    )


def _is_anywhere(state: GameState, card: object) -> bool:
    """
    Return True if some zone already holds this card.

    Cheaper answers were tried and are wrong: "is it in play" misses a card that
    went to a deck or a soul pile, and asking the card where it thinks it is
    trusts a field nothing keeps honest.
    """
    if card in cards_in_play(state):
        return True

    zones = [
        state.loot_deck,
        state.loot_discard,
        state.treasure_deck,
        state.treasure_discard,
        state.treasure_shop,
        state.monster_deck,
        state.monster_discard,
        state.room_deck,
        state.room_discard,
    ]

    for player in state.players:
        zones.extend((player.hand, player.souls))

    return any(card in zone.cards for zone in zones)
