# src/fsme/game/handler.py

"""
Game handler protocol for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Protocol

from .context import GameContext
from .result import GameResult


class GameHandler(Protocol):
    """
    Protocol implemented by all game handlers.
    """

    def execute(
        self,
        context: GameContext,
    ) -> GameResult:
        """
        Execute a game-level operation.
        """
        ...