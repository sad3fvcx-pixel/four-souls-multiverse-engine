# src/fsme/game/__init__.py

"""
Game subsystem exports.
"""

from .constants import (
    DEFAULT_MAX_PLAYERS,
    DEFAULT_MAX_TURNS,
    DEFAULT_MIN_PLAYERS,
    DEFAULT_STARTING_COINS,
    DEFAULT_STARTING_LOOT,
    DEFAULT_STARTING_TREASURES,
)
from .context import GameContext
from .dispatcher import GameDispatcher
from .errors import (
    GameError,
    GameExecutionError,
    GameInitializationError,
    GameOverError,
    InvalidGameStateError,
)
from .game import Game
from .handler import GameHandler
from .resolver import GameResolver
from .result import GameResult
from .utils import (
    ensure_game,
    game_name,
    is_game,
)

__all__ = [
    "Game",
    "GameContext",
    "GameDispatcher",
    "GameHandler",
    "GameResolver",
    "GameResult",
    "GameError",
    "GameInitializationError",
    "GameExecutionError",
    "InvalidGameStateError",
    "GameOverError",
    "DEFAULT_MIN_PLAYERS",
    "DEFAULT_MAX_PLAYERS",
    "DEFAULT_STARTING_COINS",
    "DEFAULT_STARTING_LOOT",
    "DEFAULT_STARTING_TREASURES",
    "DEFAULT_MAX_TURNS",
    "ensure_game",
    "game_name",
    "is_game",
]