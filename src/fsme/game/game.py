# src/fsme/game/game.py

"""
Session facade for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from fsme.cards import CardRegistry
from fsme.commands import Command, CommandResult, CommandType
from fsme.content import ContentLibrary
from fsme.events import Event, EventType
from fsme.rng.rng import RNG
from fsme.runtime import Runtime
from fsme.state import GameState


class Game:
    """
    One game, from the outside.

    This is the object a user interface, an AI or a network layer talks to. It
    owns nothing of its own: the state lives in GameState and the rules run in
    the Runtime. Its whole job is to be a small, stable surface in front of
    them, so that adding an engine capability does not change how a client
    starts a game or submits a move.
    """

    def __init__(
        self,
        state: GameState | None = None,
        *,
        cards: CardRegistry | None = None,
        seed: int | None = None,
        interactive_priority: bool = False,
        rng: RNG | None = None,
    ) -> None:
        game_state = state if state is not None else GameState()

        if seed is not None:
            game_state.seed = seed

        self._runtime = Runtime(
            game_state,
            cards=cards,
            rng=rng if rng is not None else RNG(game_state.seed),
            interactive_priority=interactive_priority,
        )

    @classmethod
    def from_content(
        cls,
        library: ContentLibrary,
        players: Sequence[str],
        *,
        seed: int = 0,
        interactive_priority: bool = False,
        rng: RNG | None = None,
    ) -> Game:
        """
        Lay out a game from loaded content and hand back the session.

        This is the shortest honest path from a directory of card files to a
        playable game: load, validate, deal, play.

        The deal always comes from the seed. ``rng`` replaces the generator the
        game runs on afterwards, which is how a test scripts the dice and how a
        restored game carries on from a saved generator state; leaving it out
        is the ordinary case, where the seed is the whole story.
        """
        from fsme.rules import new_game

        state = new_game(library, players, seed=seed)

        return cls(
            state,
            cards=library.registry(),
            interactive_priority=interactive_priority,
            rng=rng,
        )

    @property
    def runtime(self) -> Runtime:
        return self._runtime

    @property
    def state(self) -> GameState:
        return self._runtime.state

    @property
    def is_over(self) -> bool:
        return self.state.game_over

    @property
    def winner(self) -> int | None:
        return self.state.winner

    @property
    def awaiting_priority(self) -> bool:
        return self._runtime.awaiting_priority

    @property
    def history(self) -> tuple[Event, ...]:
        return self._runtime.history

    @property
    def command_log(self) -> tuple[CommandResult, ...]:
        return self._runtime.command_log

    def start(self, player: int = 0) -> CommandResult:
        """
        Begin the game.
        """
        return self.submit(Command(type=CommandType.START_GAME, player=player))

    def submit(self, command: Command) -> CommandResult:
        """
        Send a command to the engine.
        """
        return self._runtime.submit(command)

    def act(
        self,
        command_type: CommandType,
        player: int,
        **payload: Any,
    ) -> CommandResult:
        """
        Build and submit a command in one step.
        """
        return self.submit(
            Command(type=command_type, player=player, payload=payload)
        )

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], Any],
    ) -> None:
        """
        Observe engine events. Observers never change the game.
        """
        self._runtime.subscribe(event_type, handler)
