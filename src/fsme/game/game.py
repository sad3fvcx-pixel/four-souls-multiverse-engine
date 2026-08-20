# src/fsme/game/game.py

"""
Session facade for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from fsme.cards import CardRegistry
from fsme.commands import Command, CommandResult, CommandType
from fsme.content import ContentLibrary
from fsme.events import Event, EventType
from fsme.rng.rng import RNG
from fsme.runtime import Runtime
from fsme.scenario import Scenario
from fsme.state import GameState


def narrow(
    library: ContentLibrary,
    scenario: Scenario | None,
) -> ContentLibrary:
    """
    The content a scenario asks to play with.

    Two steps that already existed and had never been put together: choosing
    the sets, and leaving cards out of them. Neither loads anything — the
    library in hand is rearranged — so this is cheap enough to do per game.

    Handed no scenario, or one that asks for nothing, it hands the library
    straight back. The identity matters: `Game.from_content` calls this
    unconditionally, and a copy would be a different registry for no reason.
    """
    if scenario is None:
        return library

    chosen = library

    if scenario.content.expansions:
        chosen = chosen.only(scenario.content.expansions)

    if scenario.content.exclude_cards:
        chosen = chosen.without(scenario.content.exclude_cards)

    return chosen


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
        scenario: Scenario | None = None,
    ) -> Game:
        """
        Lay out a game from loaded content and hand back the session.

        This is the shortest honest path from a directory of card files to a
        playable game: load, validate, deal, play.

        The deal always comes from the seed. ``rng`` replaces the generator the
        game runs on afterwards, which is how a test scripts the dice and how a
        restored game carries on from a saved generator state; leaving it out
        is the ordinary case, where the seed is the whole story.

        ``scenario`` is somebody's experiment: which sets are in the decks, who
        sits where, what the table is worth winning. It is applied here because
        this is the one door — Watch, Study, Replay and the analysers all come
        through this method, and a scenario applied anywhere else would have to
        be applied four times.

        **With no scenario this deals exactly what it dealt before there were
        any**, which is what lets every measurement the project has taken stay
        comparable. An empty scenario is the same as none.
        """
        from fsme.rules import new_game

        chosen = narrow(library, scenario)

        state = new_game(library=chosen, players=players, seed=seed, scenario=scenario)

        return cls(
            state,
            cards=chosen.registry(),
            interactive_priority=interactive_priority,
            rng=rng,
        )

    def save(self, *, engine_version: str = "") -> dict[str, Any]:
        """
        Write the game out as plain data that can be reloaded later.

        The generator's position is taken from the live game rather than from
        GameState: the Runtime owns it while a game is running, and a save that
        forgot it would reload into a game that rolls different dice.
        """
        from fsme.serialization import save_game

        return save_game(
            self._runtime.state,
            engine_version=engine_version,
            rng_state=self._runtime.rng.get_state(),
        )

    @classmethod
    def load(
        cls,
        data: Mapping[str, Any],
        library: ContentLibrary,
        *,
        interactive_priority: bool = False,
    ) -> Game:
        """
        Rebuild a saved game against the content it was played with.

        The cards come from the library, not from the file: a save holds what
        happened to a card, never what is printed on it, so reloading against
        different content is a content mismatch and is refused as one.
        """
        from fsme.rng.rng import RNG
        from fsme.serialization import load_game

        registry = library.registry()
        state = load_game(data, registry)

        rng = RNG(state.seed)

        if state.rng_state is not None:
            rng.set_state(state.rng_state)

        return cls(
            state,
            cards=registry,
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
