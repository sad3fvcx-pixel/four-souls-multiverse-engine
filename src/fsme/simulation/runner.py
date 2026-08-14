# src/fsme/simulation/runner.py

"""
Playing a great many games.

One game is a demonstration; a thousand are evidence. This runs them — each
from its own seed, each through the ordinary engine, each producing the same
journal a game played by hand would — and hands them one at a time to whoever
is counting.

Journals are handed over and dropped rather than collected. A thousand games is
a hundred megabytes of them, and a tally is a few kilobytes; keeping the tally
and letting the journals go is the difference between a run that scales and one
that runs out of memory at ten thousand.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.journal import Journal, JournalKeeper

from .agent import ScriptedAgent

NAMES = ("Ann", "Bo", "Cy", "Di")

DEFAULT_STEPS = 6000
"""
How long one game is given before it is abandoned.

Games end well within this; the limit is here so that a run of ten thousand
cannot be stopped for ever by one of them. A game that hits it is reported as
unfinished rather than quietly counted as anything.
"""


@dataclass(frozen=True, slots=True)
class Outcome:
    """
    One game, in the few facts a run is made of.
    """

    seed: int
    players: int

    finished: bool
    winner: int | None
    turns: int
    commands: int

    journal: Journal
    """
    The whole game, handed over for counting and then dropped.

    Always present: a consumer that wants only the numbers takes them and lets
    the journal go, which is what keeps a run of ten thousand games flat in
    memory. Holding on to it is the caller's decision and the caller's cost.
    """


@dataclass(slots=True)
class Progress:
    """
    How far a run has got.
    """

    played: int = 0
    finished: int = 0
    abandoned: int = 0

    seeds_abandoned: list[int] = field(default_factory=list)


def play_one(
    library: ContentLibrary,
    seed: int,
    players: int = 2,
    *,
    steps: int = DEFAULT_STEPS,
    offers: bool = False,
) -> tuple[Journal, Game]:
    """
    Play one game to its end, keeping a journal of it.
    """
    game = Game.from_content(library, list(NAMES[:players]), seed=seed)

    game.start()

    keeper = JournalKeeper(game, offers=_offered if offers else None)

    agent = ScriptedAgent(seed)

    for _ in range(steps):
        if game.is_over:
            break

        chosen = agent.choose(game)

        if chosen is None:
            break

        command, label = chosen

        if not keeper.submit(command, label=label).accepted:
            # The agent only ever offers what the engine approved, so a refusal
            # here means the two disagree — which is a bug and not a move.
            break

    return keeper.journal, game


def _offered(game: Game) -> list[str]:
    """
    What the engine would accept right now, in the words a client would use.
    """
    from fsme.api.moves import legal_moves

    return [str(move["label"]) for move in legal_moves(game)]


def run(
    library: ContentLibrary,
    games: int,
    players: int = 2,
    *,
    first_seed: int = 0,
    steps: int = DEFAULT_STEPS,
    offers: bool = False,
    journals_into: Path | None = None,
    watching: Callable[[Progress], None] | None = None,
) -> Iterator[Outcome]:
    """
    Play a run of games, yielding each outcome as it finishes.

    Seeds run consecutively from ``first_seed``, so a run is reproducible in
    whole and in part: any game in it can be played again on its own by naming
    its seed, and it will be the same game.

    ``journals_into`` writes each journal to a file as it is produced, which is
    what a run of thousands should do if it wants to keep them: they are a
    hundred kilobytes each.
    """
    progress = Progress()

    for offset in range(games):
        seed = first_seed + offset

        journal, game = play_one(
            library, seed, players, steps=steps, offers=offers
        )

        finished = bool(game.state.game_over)

        progress.played += 1

        if finished:
            progress.finished += 1
        else:
            progress.abandoned += 1
            progress.seeds_abandoned.append(seed)

        if journals_into is not None:
            journal.save(Path(journals_into) / f"game-{seed:06d}.json")

        if watching is not None:
            watching(progress)

        yield Outcome(
            seed=seed,
            players=players,
            finished=finished,
            winner=game.state.winner,
            turns=game.state.turn.turn_number,
            commands=len(journal),
            journal=journal,
        )
