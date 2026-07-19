# src/fsme/game/errors.py

"""
Exceptions for the game subsystem.
"""

from __future__ import annotations

from fsme.util.errors import EngineError


class GameError(EngineError):
    """
    Base exception for all game-related errors.
    """


class GameInitializationError(GameError):
    """
    Raised when a game cannot be initialized.
    """


class GameExecutionError(GameError):
    """
    Raised when a game operation fails during execution.
    """


class InvalidGameStateError(GameError):
    """
    Raised when the game enters an invalid state.
    """


class GameOverError(GameError):
    """
    Raised when an operation is attempted after the game has ended.
    """