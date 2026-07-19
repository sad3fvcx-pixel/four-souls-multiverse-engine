# src/fsme/game/dispatcher.py

"""
Game dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .context import GameContext
from .handler import GameHandler
from .resolver import GameResolver
from .result import GameResult


class GameDispatcher:
    """
    Dispatches game operations to the resolver.
    """

    def __init__(
        self,
        resolver: GameResolver | None = None,
    ) -> None:
        self._resolver = resolver or GameResolver()

    @property
    def resolver(self) -> GameResolver:
        return self._resolver

    def dispatch(
        self,
        handler: GameHandler,
        context: GameContext,
    ) -> GameResult:
        """
        Dispatch a game operation for execution.
        """
        return self._resolver.resolve(
            handler,
            context,
        )

    def set_resolver(
        self,
        resolver: GameResolver,
    ) -> None:
        """
        Replace the active resolver.
        """
        self._resolver = resolver