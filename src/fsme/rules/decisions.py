# src/fsme/rules/decisions.py

"""
Answering a pending decision.
"""

from __future__ import annotations

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.state import GameState


class ChooseTargetHandler:
    """
    Records a player's answer to the question the engine is waiting on.

    The choice arrives as indices into the options the engine offered, not as
    objects. A client can only pick from what it was given, so it cannot name a
    monster that is not there or a player who has already died.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        decision = state.pending_decision

        if decision is None:
            return "nothing is waiting to be chosen"

        if decision.player != command.player:
            return (
                f"player {decision.player} is choosing, not player {command.player}"
            )

        choices = command.get("choices")

        if choices is None:
            index = command.get("index")
            choices = [index] if index is not None else None

        if not isinstance(choices, (list, tuple)):
            return "a choice must be given as 'choices' or 'index'"

        if len(set(choices)) != len(choices):
            return "the same option was chosen twice"

        if not decision.accepts(len(choices)):
            return (
                f"this choice takes between {decision.minimum} and "
                f"{decision.maximum} options, {len(choices)} given"
            )

        for choice in choices:
            if not isinstance(choice, int) or not 0 <= choice < len(decision.options):
                return f"no option at index {choice!r}"

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        decision = context.state.pending_decision

        if decision is None:
            return

        choices = command.get("choices")

        if choices is None:
            choices = [command.get("index")]

        decision.chosen = [decision.options[int(choice)] for choice in choices]
