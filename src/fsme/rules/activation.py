# src/fsme/rules/activation.py

"""
Activating treasures.
"""

from __future__ import annotations

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.events import EventType
from fsme.state import GameState


class ActivateTreasureHandler:
    """
    Taps one of a player's items and fires its activated ability.

    Activation is not restricted to the active player: an item may be used
    whenever its controller holds priority, which is what makes responding to
    something on the stack possible.
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

        if getattr(card, "tapped", False):
            return f"'{getattr(card, 'name', card)}' is already tapped"

        definition = getattr(card, "definition", None)

        if definition is None or not definition.abilities_for(
            str(EventType.ON_ACTIVATE)
        ):
            return f"'{getattr(card, 'name', card)}' has no activated ability"

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state
        player = state.player(command.player)

        card = player.treasures.cards[int(command.get("index", 0))]

        context.emit(
            EventType.BEFORE_ACTIVATE,
            source=card,
            controller=player.player_id,
        )

        context.apply("deactivate", [card])

        context.emit(
            EventType.ON_ACTIVATE,
            source=card,
            controller=player.player_id,
        )

        context.emit(
            EventType.AFTER_ACTIVATE,
            source=card,
            controller=player.player_id,
        )
