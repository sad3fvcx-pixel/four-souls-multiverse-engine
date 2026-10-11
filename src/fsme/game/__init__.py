# src/fsme/game/__init__.py

"""
Game subsystem exports.

Turn structure, phases and victory are rules, and they live in ``fsme.rules``.
What remains here is the session facade external systems talk to.
"""

from .errors import (
    GameError,
    GameExecutionError,
    GameInitializationError,
    GameOverError,
    InvalidGameStateError,
)
from .game import Game

__all__ = [
    "Game",
    "GameError",
    "GameExecutionError",
    "GameInitializationError",
    "GameOverError",
    "InvalidGameStateError",
]
