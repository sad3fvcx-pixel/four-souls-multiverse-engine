# src/fsme/game/resolver.py

"""
Game resolver for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import GameContext
from .handler import GameHandler
from .result import GameResult


class GameResolver:
    """
    Resolves game-level operations.

    Concrete game behavior will later be implemented by
    specialized handlers.
    """

    def resolve(
        self,
        handler: GameHandler,
        context: GameContext,
    ) -> GameResult:
        """
        Execute a game operation using the provided handler.
        """
        return handler.execute(context)