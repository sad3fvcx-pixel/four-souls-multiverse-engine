# src/fsme/commands/handler.py

"""
Command handler protocol for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Protocol

from fsme.effects import EffectContext
from fsme.state import GameState

from .command import Command


class CommandHandler(Protocol):
    """
    What it takes to implement one command.

    The split is deliberate. ``validate`` answers "is this legal?" by reading
    the game and nothing else; ``execute`` runs only after that answer is yes.
    Because validation never writes, a rejected command cannot leave the game
    half-changed.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        """
        Return None if the command is legal, otherwise the reason it is not.
        """
        ...

    def execute(self, command: Command, context: EffectContext) -> None:
        """
        Carry out a validated command by emitting events and pushing effects.
        """
        ...
