# src/fsme/rules/priority.py

"""
Priority passing.
"""

from __future__ import annotations

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.state import GameState


class PassPriorityHandler:
    """
    Declines to respond to the object on top of the stack.

    Once every living player has passed in a row the window closes and the
    Runtime resolves the top object. Anything other than a pass reopens the
    window, because the players who already passed must get to answer the new
    object too.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        if not state.priority.is_open:
            return "no priority window is open"

        if state.priority.holder != command.player:
            return (
                f"player {state.priority.holder} holds priority, "
                f"not player {command.player}"
            )

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state

        state.priority.record_pass(max(1, len(state.living_players())))
