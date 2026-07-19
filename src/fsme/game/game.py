# src/fsme/game/game.py

"""
Core game object for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fsme.commands import CommandBus
from fsme.events import EventBus
from fsme.stack import Stack
from fsme.state import GameState


@dataclass(slots=True)
class Game:
    """
    Root object representing a running game.
    """

    state: GameState = field(default_factory=GameState)

    events: EventBus = field(default_factory=EventBus)

    commands: CommandBus = field(default_factory=CommandBus)

    stack: Stack = field(default_factory=Stack)

    def reset(self) -> None:
        """
        Reset transient runtime state.
        """
        self.stack.clear()