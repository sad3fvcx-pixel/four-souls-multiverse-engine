# src/fsme/rules/activation.py

"""
Activating treasures.
"""

from __future__ import annotations

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.events import EventType
from fsme.state import GameState

from .costs import pay, unpayable


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

        index = command.get("index", 0)

        if not isinstance(index, int) or not 0 <= index < player.treasure_count:
            return f"no treasure at index {index!r}"

        card = player.treasures.cards[index]

        definition = getattr(card, "definition", None)

        abilities = (
            definition.abilities_for(str(EventType.ON_ACTIVATE))
            if definition is not None
            else ()
        )

        if not abilities:
            return f"'{getattr(card, 'name', card)}' has no activated ability"

        which = command.get("ability", 0)

        if not isinstance(which, int) or not 0 <= which < len(abilities):
            return f"'{getattr(card, 'name', card)}' has no ability {which!r}"

        return unpayable(abilities[which], card, player, state)

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state
        player = state.player(command.player)

        card = player.treasures.cards[int(command.get("index", 0))]
        which = int(command.get("ability", 0))

        ability = card.definition.abilities_for(str(EventType.ON_ACTIVATE))[which]

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
