# src/fsme/game/utils.py

"""
Utility functions for the game subsystem.
"""

from __future__ import annotations

from .game import Game


def ensure_game(obj: object) -> Game:
    """
    Ensure that an object is a Game instance.
    """
    if not isinstance(obj, Game):
        raise TypeError(
            f"Expected Game, got {type(obj).__name__}."
        )

    return obj


def game_name(game: Game) -> str:
    """
    Return a human-readable game name.
    """
    return game.__class__.__name__


def is_game(obj: object) -> bool:
    """
    Check whether an object is a Game instance.
    """
    return isinstance(obj, Game)