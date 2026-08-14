# src/fsme/simulation/pool.py

"""
Running games on more than one core.

A game is entirely its own: a seed, a library and nothing shared. So a run is
embarrassingly parallel, and the only care needed is that it stay *the same*
run — the same seeds giving the same games, and the same numbers coming out
however the work was divided.

That care is in two places. Each worker plays whole games, so nothing about a
game is split across processes. And what comes back is a tally rather than a
journal, so the parent adds up small things in whatever order they finish —
addition does not mind the order, which is why the answer does not either.
"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from fsme.analysis import Tally

from .runner import DEFAULT_STEPS, play_one

_library = None
_root: Path | None = None
_drop: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Finished:
    """
    One game played somewhere else, in what came back from it.
    """

    seed: int
    finished: bool
    winner: int | None
    turns: int
    commands: int

    tally: Tally

    broke: str = ""
    """
    Why this game stopped, when it stopped by falling over.

    A run of a thousand games must not be lost to one of them, and a game that
    raised is a finding rather than an accident — the whole point of playing
    thousands is to reach positions nobody thought to write a test for. So it
    is caught here, counted, and named by its seed, which is enough to go back
    and watch it happen.
    """


def _prepare(root: str, drop: tuple[str, ...]) -> None:
    """
    Load the content once per worker.

    A worker plays many games and the library never changes, so loading it
    per game would cost more than the games do.
    """
    global _library, _root, _drop

    from fsme.api import load_content

    _root = Path(root)
    _drop = frozenset(drop)

    loaded = load_content(_root)

    _library = loaded.without(_drop) if _drop else loaded


def _one(work: tuple[int, int, int, str | None, bool, tuple[int, ...]]) -> Finished:
    """
    Play one game in a worker and send back what was counted.
    """
    seed, players, steps, journals_into, offers, thinking_seats = work

    if _library is None:
        raise RuntimeError("this worker was never given any content")

    try:
        journal, game = play_one(
            _library,
            seed,
            players,
            steps=steps,
            offers=offers,
            thinking_seats=thinking_seats,
        )
    except Exception as error:  # noqa: BLE001 - a game that falls over is data
        return Finished(
            seed=seed,
            finished=False,
            winner=None,
            turns=0,
            commands=0,
            tally=Tally(),
            broke=f"{type(error).__name__}: {error}",
        )

    if journals_into:
        journal.save(Path(journals_into) / f"game-{seed:06d}.json")

    tally = Tally()
    tally.add(journal)

    return Finished(
        seed=seed,
        finished=bool(game.state.game_over),
        winner=game.state.winner,
        turns=game.state.turn.turn_number,
        commands=len(journal),
        tally=tally,
    )


def run_on_many_cores(
    root: Path,
    games: int,
    players: int = 2,
    *,
    jobs: int = 2,
    first_seed: int = 0,
    steps: int = DEFAULT_STEPS,
    offers: bool = False,
    journals_into: Path | None = None,
    without: tuple[str, ...] = (),
    thinking_seats: tuple[int, ...] = (),
) -> Iterator[Finished]:
    """
    Play a run across several processes, yielding each game as it finishes.

    The content is named by its directory rather than handed over: a loaded
    library is a large object and every worker needs its own anyway.

    Games come back in whatever order they finish. Nothing downstream may
    depend on that order, which is why what comes back is a tally.
    """
    work = [
        (
            first_seed + offset,
            players,
            steps,
            str(journals_into) if journals_into else None,
            offers,
            thinking_seats,
        )
        for offset in range(games)
    ]

    with ProcessPoolExecutor(
        max_workers=max(1, jobs),
        initializer=_prepare,
        initargs=(str(root), tuple(without)),
    ) as pool:
        yield from pool.map(_one, work, chunksize=_chunk(games, jobs))


def _chunk(games: int, jobs: int) -> int:
    """
    How many games to hand a worker at a time.

    Games are seconds long and handing them over costs microseconds, so the
    chunk exists only to keep the last worker from being handed a pile while
    the others stand idle. A few per worker is the whole of the tuning.
    """
    return max(1, games // (max(1, jobs) * 4))
