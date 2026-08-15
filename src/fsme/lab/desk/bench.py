# src/fsme/lab/desk/bench.py

"""
The four things a person actually wants to do, run in the background.

A study of two hundred games takes half a minute and a card test takes two.
Neither can happen inside an HTTP request that a browser is waiting on, so each
becomes a *job*: it is started, it says how far it has got, and it ends holding
the same text the command line would have printed.

That last part is the design rule here. The desk runs the identical functions
the CLI runs and shows their identical output. A button that produced a
slightly different answer from the command would make two sources of truth out
of one, and the first disagreement between them would be unanswerable.

Nothing in this module decides anything about the game either. It starts
threads, counts progress and holds text.
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fsme.content import ContentLibrary
from fsme.journal import Journal

WAITING = "waiting"
RUNNING = "running"
DONE = "done"
FAILED = "failed"


@dataclass(slots=True)
class Job:
    """
    One piece of work, and everything a page needs to draw it.
    """

    id: int
    kind: str
    title: str

    state: str = WAITING

    done: int = 0
    total: int = 0

    text: str = ""
    """The report, exactly as the command line would have printed it."""

    error: str = ""

    saved: str = ""
    """Where the journal went, when the job produced one."""

    @property
    def share(self) -> float:
        return min(1.0, self.done / self.total) if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "state": self.state,
            "done": self.done,
            "total": self.total,
            "share": self.share,
            "text": self.text,
            "error": self.error,
            "saved": self.saved,
        }


class Workbench:
    """
    Somewhere to put work that takes longer than a click.

    One lock guards the job table; the work itself runs outside it, because a
    card test holding a lock for two minutes would stop the page redrawing.
    """

    def __init__(self, library: ContentLibrary, root: Path, work: Path) -> None:
        self._library = library
        self._root = root
        self._work = work

        self._lock = threading.Lock()
        self._jobs: dict[int, Job] = {}
        self._next = 1

    @property
    def work(self) -> Path:
        return self._work

    def jobs(self) -> list[Job]:
        """
        Every job, newest first.
        """
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: -job.id)

    def job(self, number: int) -> Job | None:
        with self._lock:
            return self._jobs.get(number)

    def journals(self) -> list[dict[str, Any]]:
        """
        The games on disk that a report could be opened from.
        """
        if not self._work.is_dir():
            return []

        found = sorted(
            self._work.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        return [
            {"name": path.name, "size": path.stat().st_size} for path in found
        ]

    def cards(self) -> list[dict[str, str]]:
        """
        Every card the content holds, for a box that completes as you type.
        """
        return sorted(
            (
                {"id": definition.id, "name": definition.name}
                for definition in self._library.definitions()
            ),
            key=lambda card: card["name"],
        )

    # ------------------------------------------------------------------
    # The four things
    # ------------------------------------------------------------------

    def play(self, seed: int, players: int, bot_seats: tuple[int, ...]) -> Job:
        """
        Play one game to the end and report on it.
        """
        return self._start(
            "play",
            f"a game — seed {seed}, {players} players",
            lambda job: self._play(job, seed, players, bot_seats),
        )

    def study(
        self, games: int, players: int, jobs: int, bot_seats: tuple[int, ...]
    ) -> Job:
        """
        Play a run and ask it what it says about the game.
        """
        return self._start(
            "study",
            f"a study — {games} games, {players} players",
            lambda job: self._study(job, games, players, jobs, bot_seats),
        )

    def test_card(self, card: str, games: int, players: int, jobs: int) -> Job:
        """
        Play the same seeds with a card and without it.
        """
        return self._start(
            "test-card",
            f"a card test — {card}, {games} games each way",
            lambda job: self._test_card(job, card, games, players, jobs),
        )

    def open_report(self, name: str) -> Job:
        """
        Read a saved game every way the lab knows how.
        """
        return self._start(
            "report",
            f"a report — {name}",
            lambda job: self._report(job, name),
        )

    # ------------------------------------------------------------------

    def _start(self, kind: str, title: str, work: Callable[[Job], None]) -> Job:
        with self._lock:
            job = Job(id=self._next, kind=kind, title=title)

            self._jobs[job.id] = job
            self._next += 1

        def run() -> None:
            job.state = RUNNING

            try:
                work(job)
            except Exception:
                job.state = FAILED
                job.error = traceback.format_exc(limit=3)
            else:
                job.state = DONE

        threading.Thread(target=run, daemon=True).start()

        return job

    def _play(
        self, job: Job, seed: int, players: int, bot_seats: tuple[int, ...]
    ) -> None:
        from fsme.lab.analysis import review, reviewed
        from fsme.lab.simulation import play_one

        job.total = 1

        journal, _ = play_one(
            self._library, seed, players, thinking_seats=bot_seats
        )

        self._work.mkdir(parents=True, exist_ok=True)

        where = self._work / f"game-{seed}-{players}p.json"
        journal.save(where)

        job.saved = where.name
        job.done = 1
        job.text = reviewed(review(journal, self._library))

    def _study(
        self,
        job: Job,
        games: int,
        players: int,
        jobs: int,
        bot_seats: tuple[int, ...],
    ) -> None:
        from fsme.lab.analysis import study as ask
        from fsme.lab.analysis import written
        from fsme.lab.simulation import run_on_many_cores

        job.total = games

        names = {
            definition.id: definition.name
            for definition in self._library.definitions()
        }

        summaries = []

        for done in run_on_many_cores(
            self._root,
            games,
            players,
            jobs=max(1, jobs),
            offers=True,
            thinking_seats=bot_seats,
        ):
            job.done += 1

            if done.summary is not None and not done.broke:
                summaries.append(done.summary)

        job.text = written(ask(summaries, names=names))

    def _test_card(
        self, job: Job, card: str, games: int, players: int, jobs: int
    ) -> None:
        from fsme.lab.analysis import Tally, compare, read_out
        from fsme.lab.simulation import run_on_many_cores

        named = self._library.registry().get(card)

        # Both runs, so the bar means what it says.
        job.total = games * 2

        runs: dict[str, Tally] = {}
        appeared = 0

        for label, drop in (("with", ()), ("without", (card,))):
            tally = Tally()

            for done in run_on_many_cores(
                self._root,
                games,
                players,
                jobs=max(1, jobs),
                without=drop,
            ):
                job.done += 1
                tally.merge(done.tally)

            runs[label] = tally

            if label == "with":
                seen = tally.cards.get(card)
                appeared = seen.games if seen else 0

        job.text = read_out(
            compare(
                f"{named.name} ({card})",
                runs["with"],
                runs["without"],
                appeared=appeared,
            )
        )

    def _report(self, job: Job, name: str) -> None:
        from fsme.lab.analysis import review, reviewed

        job.total = 1

        where = self._safe(name)

        journal = Journal.load(where)

        job.saved = where.name
        job.done = 1
        job.text = reviewed(review(journal, self._library))

    def _safe(self, name: str) -> Path:
        """
        Turn a name from a browser into a path inside the work directory.

        The browser is on the same machine as the server and is nobody's enemy,
        but a name is still a string somebody typed, and ``../../etc/passwd``
        is a string somebody typed.
        """
        where = (self._work / Path(name).name).resolve()

        if where.parent != self._work.resolve():
            raise ValueError(f"{name!r} is not in the work directory")

        return where
