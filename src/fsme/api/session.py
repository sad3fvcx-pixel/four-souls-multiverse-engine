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

from pathlib import Path
from typing import Any

from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.game import Game
from fsme.journal import Journal, JournalKeeper
from fsme.runtime.vocabulary import engine_vocabulary

from .moves import legal_moves
from .view import events, snapshot

DEFAULT_PLAYERS = ("Ann", "Bo", "Cy", "Di")


def load_content(root: Path) -> ContentLibrary:
    """
    Read every card the engine knows about from a content directory.
    """
    return ContentLoader(engine_vocabulary()).load_root(root)


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
    ) -> None:
        if not 2 <= players <= len(DEFAULT_PLAYERS):
            raise ValueError(
                f"a game takes between 2 and {len(DEFAULT_PLAYERS)} players"
            )

        self._library = library
        self._players = players
        self._seed = seed
        self._interactive = interactive_priority
        self._names = list(names or DEFAULT_PLAYERS[:players])

        self._game = self._new_game()

    def _new_game(self) -> Game:
        game = Game.from_content(
            self._library,
            self._names,
            seed=self._seed,
            interactive_priority=self._interactive,
        )

        game.start()

        # The journal is kept from the deal onwards, without the alternatives:
        # a client already knows what it offered, and asking the engine again
        # before every click would double the work of playing.
        self._keeper = JournalKeeper(game)

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

    def restart(self, *, seed: int | None = None, players: int | None = None) -> None:
        """
        Throw the game away and deal another one.
        """
        if seed is not None:
            self._seed = int(seed)

        if players is not None:
            if not 2 <= players <= len(DEFAULT_PLAYERS):
                raise ValueError(
                    f"a game takes between 2 and {len(DEFAULT_PLAYERS)} players"
                )

            self._players = int(players)
            self._names = list(DEFAULT_PLAYERS[: self._players])

        self._game = self._new_game()

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
