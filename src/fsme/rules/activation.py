# src/fsme/rules/activation.py

"""
Activating a card that taps for something.

An item is the usual one, but not the only one: a character card taps for its
ability, and so does a room. What they have in common is the whole mechanic —
a printed "↷: do this" and one use until it recharges — so they share the
command, and the command says which card it means.
"""

from __future__ import annotations

from typing import Any

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.events import EventType
from fsme.state import GameState

from .costs import pay, unpayable
from .restrictions import ACTIVATE, refuse

TREASURES = "treasures"
"""The item area, which is where a card is activated from unless it is not."""

CHARACTER = "character"
"""A player's own character card, which taps for its ability like an item."""

ROOM = "room"
"""
The room in play, which belongs to nobody and is used by the active player.

COMPREHENSIVE_RULES.md §12: an activated ability of a room may only be
activated by the active player. A room belongs to the table rather than to
anybody at it, and this is the rule that says whose turn it is to use one.
"""


def _zone_of(command: Command) -> str:
    return str(command.get("zone", TREASURES))


def _card_for(command: Command, state: GameState) -> tuple[Any | None, str | None]:
    """
    Find the card a command means, or say why there is not one.
    """
    zone = _zone_of(command)
    player = state.player(command.player)

    if zone == CHARACTER:
        return player.character, (
            None if player.character is not None else "this player has no character card"
        )

    if zone == ROOM:
        if command.player != state.turn.active_player:
            return None, "only the active player may use the room"

        index = command.get("index", 0)

        if not isinstance(index, int) or not 0 <= index < len(state.room_area):
            return None, f"no room at index {index!r}"

        return state.room_area.cards[index], None

    index = command.get("index", 0)

    if not isinstance(index, int) or not 0 <= index < player.treasure_count:
        return None, f"no treasure at index {index!r}"

    return player.treasures.cards[index], None


class ActivateTreasureHandler:
    """
    Pays for one of a player's items and fires its activated ability.

    Activation is not restricted to the active player: an item may be used
    whenever its controller holds priority, which is what makes responding to
    something on the stack possible.

    An item may print more than one activated ability — a tap ability and a
    paid one, as Tech X and The Bone do — so the command names which, and only
    that one fires.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        if not state.started:
            return "the game has not started"

        if state.game_over:
            return "the game is over"

        player = state.player(command.player)

        if not player.alive:
            return "a dead player may not activate items"

        card, refusal = _card_for(command, state)

        if refusal is not None:
            return refusal

        # The face, not the definition: an item copying another item is
        # activated for the ability it is currently wearing.
        face = getattr(card, "face", None)

        abilities = (
            face.abilities_for(str(EventType.ON_ACTIVATE)) if face is not None else ()
        )

        if not abilities:
            return f"'{getattr(card, 'name', card)}' has no activated ability"

        which = command.get("ability", 0)

        if not isinstance(which, int) or not 0 <= which < len(abilities):
            return f"'{getattr(card, 'name', card)}' has no ability {which!r}"

        forbidden = refuse(state, ACTIVATE, player=command.player)

        if forbidden is not None:
            return forbidden

        return unpayable(abilities[which], card, player, state)

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state
        player = state.player(command.player)

        card, _ = _card_for(command, state)

        if card is None:
            return

        which = int(command.get("ability", 0))

        ability = card.face.abilities_for(str(EventType.ON_ACTIVATE))[which]

        context.emit(
            EventType.BEFORE_ACTIVATE,
            source=card,
            controller=player.player_id,
            ability_index=which,
        )

        pay(ability, card, context)

        # The event carries which ability was used, so an item with two of them
        # fires the one that was paid for and not the other.
        context.emit(
            EventType.ON_ACTIVATE,
            source=card,
            controller=player.player_id,
            ability_index=which,
        )

        context.emit(
            EventType.AFTER_ACTIVATE,
            source=card,
            controller=player.player_id,
            ability_index=which,
        )
