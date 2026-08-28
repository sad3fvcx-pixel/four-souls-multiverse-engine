# src/fsme/api/session.py

"""
One game, held for a client to talk to.

A session owns a Game and nothing else. It starts one, forwards commands into
it, and hands back the view — it does not decide anything, does not remember
anything the game already remembers, and has no opinion about whose turn it is.

Everything a client is allowed to do is a method here, and every one of them is
a thin pass to the engine. That is the boundary: if a rule ever needs stating
to make a client work, it belongs in ``fsme.rules``, not in this file.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.content.library import Expansion
from fsme.game import Game
from fsme.journal import Journal, JournalKeeper
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.scenario import Scenario
from fsme.util.errors import EngineError

from .moves import legal_moves
from .view import events, snapshot

DEFAULT_PLAYERS = ("Ann", "Bo", "Cy", "Di")


def load_content(root: Path | Sequence[Path | str]) -> ContentLibrary:
    """
    Read every card the engine knows about.

    One directory, or several read into one library — the cards FSME ships
    live in one place and the cards somebody writes live in another, and a
    game deals from both without knowing the difference.
    """
    roots = [root] if isinstance(root, (str, Path)) else list(root)

    return ContentLoader(engine_vocabulary()).load_roots(roots)


def _named_sets(
    library: ContentLibrary, asked: Sequence[str]
) -> tuple[str, ...]:
    """
    The sets somebody asked to play with, checked against what was loaded.

    An empty list means all of them, which is what a page sends when nothing is
    ticked. A name nothing loaded is a mistake worth saying out loud: the
    likeliest reason is a set that failed to load, and dealing without it
    silently is how somebody comes to watch a game their cards are not in.
    """
    wanted = tuple(str(one) for one in asked if str(one))

    if not wanted:
        return ()

    missing = [one for one in wanted if one not in library.expansions]

    if missing:
        known = ", ".join(sorted(library.expansions)) or "nothing at all"

        raise ValueError(
            f"no set called {missing[0]!r} was loaded — there is {known}"
        )

    return wanted


class Session:
    """
    A game and the small set of things a client may ask of it.
    """

    def __init__(
        self,
        library: ContentLibrary,
        players: int = 2,
        *,
        seed: int = 0,
        interactive_priority: bool = True,
        names: list[str] | None = None,
        scenario: Scenario | None = None,
    ) -> None:
        if not 2 <= players <= len(DEFAULT_PLAYERS):
            raise ValueError(
                f"a game takes between 2 and {len(DEFAULT_PLAYERS)} players"
            )

        self._library = library
        self._chosen: tuple[str, ...] = ()
        self._players = players
        self._seed = seed
        self._scenario = scenario
        self._interactive = interactive_priority
        self._names = list(names or DEFAULT_PLAYERS[:players])

        if scenario is not None and scenario.interactive_priority is not None:
            self._interactive = scenario.interactive_priority

        self._game = self._new_game()

    @property
    def playing(self) -> ContentLibrary:
        """
        The cards this session is actually dealing from.

        Everything loaded, unless somebody has narrowed it to a few sets. The
        whole library is kept either way: narrowing is a choice about this
        game, not about what was loaded, and widening it again must not need
        the files read a second time.
        """
        if not self._chosen:
            return self._library

        return self._library.only(self._chosen)

    @property
    def sets(self) -> tuple[Expansion, ...]:
        """
        Every set that was loaded, whoever wrote it.

        A card somebody made is loaded exactly like a card FSME ships, so this
        does not say which is which — the author named their own set and knows
        it by that name.
        """
        return tuple(
            self._library.expansions[key]
            for key in sorted(self._library.expansions)
        )

    @property
    def chosen(self) -> tuple[str, ...]:
        """
        The sets this session was narrowed to, empty when it was not.
        """
        return self._chosen

    def _new_game(self) -> Game:
        game = Game.from_content(
            self.playing,
            self._names,
            seed=self._seed,
            interactive_priority=self._interactive,
            scenario=self._scenario,
        )

        # The keeper is built before the deal rather than after it, so that the
        # deal is in the journal like everything else. It was not: the opening
        # hands, the starting cents and the first loot all happened before
        # anything was writing, and a journal that began at the second move was
        # not a record of the game.
        #
        # The alternatives are left out. A client already knows what it offered,
        # and asking the engine again before every click would double the work
        # of playing.
        self._keeper = JournalKeeper(game)

        self._keeper.submit(
            Command(type=CommandType.START_GAME, player=0),
            label="The game is dealt",
        )

        return game

    @property
    def game(self) -> Game:
        return self._game

    @property
    def journal(self) -> Journal:
        """
        The story of the game so far.
        """
        return self._keeper.journal

    @property
    def scenario(self) -> Scenario | None:
        """
        The experiment this session is running, if it is running one.
        """
        return self._scenario

    def restart(
        self,
        *,
        seed: int | None = None,
        players: int | None = None,
        sets: Sequence[str] | None = None,
    ) -> None:
        """
        Throw the game away and deal another one.

        The scenario stays: restarting is dealing the same experiment again,
        not leaving it.

        ``sets`` narrows the deal to the sets named, and an empty list widens
        it back to everything loaded. Nothing is read again either way: the
        library already holds every set, and this only decides which of them
        this game is dealt from. A set that was never loaded is refused rather
        than ignored, because a game quietly dealt without the cards somebody
        asked for is the bug this exists to fix.

        A choice that cannot be dealt — one set on its own with no treasures in
        it — is refused and *put back*. Leaving the session narrowed to content
        no game can be made from would break every restart after it, including
        the one that would have undone the mistake.
        """
        was = self._chosen

        if sets is not None:
            self._chosen = _named_sets(self._library, sets)

        if seed is not None:
            self._seed = int(seed)

        if players is not None:
            if not 2 <= players <= len(DEFAULT_PLAYERS):
                raise ValueError(
                    f"a game takes between 2 and {len(DEFAULT_PLAYERS)} players"
                )

            self._players = int(players)
            self._names = list(DEFAULT_PLAYERS[: self._players])

        try:
            self._game = self._new_game()
        except EngineError:
            self._chosen = was

            raise

    def view(self, since: int = 0) -> dict[str, Any]:
        """
        The whole position, the moves available, and the log since a point.
        """
        return {
            "state": snapshot(self._game),
            "moves": legal_moves(self._game),
            "events": events(self._game, since),
            "history_length": len(self._game.history),
        }

    def submit(self, command: dict[str, Any]) -> dict[str, Any]:
        """
        Send one command into the game and report what the engine made of it.
        """
        kind = self._command_type(str(command.get("type", "")))

        result = self._keeper.submit(
            Command(
                type=kind,
                player=int(command.get("player", 0)),
                payload=dict(command.get("payload", {})),
            ),
            label=str(command.get("label", "")),
        )

        return {"accepted": bool(result.accepted), "reason": result.reason or ""}

    @staticmethod
    def _command_type(name: str) -> CommandType:
        for kind in CommandType:
            if str(kind) == name:
                return kind

        raise ValueError(f"unknown command '{name}'")

    def save(self) -> dict[str, Any]:
        return dict(self._game.save())

    def load(self, data: dict[str, Any]) -> None:
        self._game = Game.load(data, self._library)
