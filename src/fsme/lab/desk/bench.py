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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fsme.content import ContentLibrary
from fsme.journal import Journal


def _version() -> str:
    from fsme.cli.main import VERSION

    return VERSION

REPORT_FORMAT = 1
"""
The version of the file `Save report` writes.

Bumped when the shape changes in a way an older FSME could not read. What makes
this worth versioning at all is that the file is not a report — it is the
*game*, with the report alongside for reading. The analysers are re-run when it
is loaded, so a file saved today gets today's turning points and tomorrow's
improvements to them.
"""

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

    def show_card(self, card: Mapping[str, Any]) -> list[dict[str, Any]]:
        """
        Play one card in a game and say what happened, moment by moment.

        Not the same question as "does this card change how games go" — that
        is a study, takes two minutes, and answers with statistics. This is the
        first question anybody has about a card they just made: *does it do
        what I meant?* So the card is put into a hand and played, and what the
        engine announced is read back in plain sentences.

        A card that is never dealt teaches nobody anything, which is why it is
        placed rather than shuffled for.
        """
        from fsme.cards import CardDefinition, CardInstance
        from fsme.commands import Command, CommandType
        from fsme.game import Game

        definition = CardDefinition.from_data(dict(card))
        game = Game.from_content(self._library, ["You", "Bea", "Cass", "Dee"], seed=5)
        game.start()

        held = CardInstance(
            definition=definition,
            instance_id=game.state.ids.allocate("preview"),
            controller=0,
            owner=0,
        )
        before = _snapshot(game)

        if str(definition.type) == "loot":
            game.state.player(0).hand.add_top(held)
            index = list(game.state.player(0).hand.cards).index(held)
            game.submit(
                Command(
                    type=CommandType.PLAY_LOOT, player=0, payload={"index": index}
                )
            )
        else:
            game.state.player(0).treasures.add_top(held)

        for _ in range(20):
            waiting = game.runtime.awaiting_decision

            if waiting is None:
                break

            game.submit(
                Command(
                    type=CommandType.CHOOSE_TARGET,
                    player=waiting.player,
                    payload={"choices": [0]},
                )
            )

        return _what_changed(before, _snapshot(game), definition.name)

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

    def cards(self) -> list[dict[str, Any]]:
        """
        Every card the content holds, for choosing one to test.

        Three fields rather than one, because a name alone cannot identify a
        card: twelve cards are called "Pills!" and six are called "Eden". The
        set says which, and whether the engine has rules for it says whether
        testing it can tell you anything — a card with no behaviour will always
        come back "no effect", and finding that out after a two-minute run is a
        waste nobody should have to discover twice.
        """
        return sorted(
            (
                {
                    "id": definition.id,
                    "name": definition.name,
                    "set": definition.expansion,
                    "implemented": bool(
                        definition.abilities or definition.statics
                    ),
                    "text": str(definition.metadata.get("text", "")),
                }
                for definition in self._library.definitions()
            ),
            key=lambda card: (str(card["name"]).lower(), str(card["set"])),
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

    def bundle(self, number: int) -> dict[str, Any] | None:
        """
        A finished job, packed into a file somebody can keep or send on.

        The journal is the point of it. Saving only the text would make a
        souvenir: nobody could ask a different question of it later, and every
        analyser in the project reads games rather than prose. So the game
        travels, and the report travels beside it as what it looked like at the
        time.
        """
        job = self.job(number)

        if job is None or job.state != DONE or not job.saved:
            return None

        where = self._safe(job.saved)

        if not where.is_file():
            return None

        import json

        return {
            "fsme_report": REPORT_FORMAT,
            "fsme_version": _version(),
            "kind": job.kind,
            "title": job.title,
            "text": job.text,
            "journal": json.loads(where.read_text("utf-8")),
        }

    def take_bundle(self, given: Any) -> Job:
        """
        Read a saved report back, and report on the game inside it again.

        What is checked, in the order somebody would want to hear it: that the
        file is one of ours, that this FSME is new enough to read it, and that
        the game inside is a journal this engine understands. Each of those
        gets its own sentence rather than one "invalid file".
        """
        if not isinstance(given, dict) or "fsme_report" not in given:
            raise ValueError(
                "that is not an FSME report — a report is the file the"
                " Save report button writes"
            )

        format_version = given.get("fsme_report")

        if not isinstance(format_version, int) or format_version > REPORT_FORMAT:
            raise ValueError(
                f"that report is written in format {format_version}, and this"
                f" FSME reads format {REPORT_FORMAT}. It was saved by a newer"
                f" version."
            )

        if not isinstance(given.get("journal"), dict):
            raise ValueError(
                "that report has no game in it, so there is nothing to analyse"
            )

        return self._start(
            "report",
            f"a saved report — {given.get('title') or 'a game'}",
            lambda job: self._loaded(job, given),
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

    def _loaded(self, job: Job, given: dict[str, Any]) -> None:
        """
        Put the game from a saved report back on disk, and read it again.

        Re-run rather than replayed from the stored text: the file carries the
        game, so a report loaded into a later FSME is that FSME's report.
        """
        import json

        from fsme.lab.analysis import review, reviewed

        job.total = 1

        self._work.mkdir(parents=True, exist_ok=True)

        journal = Journal.from_dict(given["journal"])

        where = self._work / f"loaded-{journal.seed}-{len(journal.players)}p.json"
        where.write_text(json.dumps(given["journal"]), encoding="utf-8")

        job.saved = where.name
        job.done = 1
        job.text = reviewed(review(journal, self._library))

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


def _snapshot(game: Any) -> dict[str, Any]:
    """
    The few numbers a person watching a card would look at.
    """
    return {
        "coins": [player.pennies for player in game.state.players],
        "hp": [player.hp for player in game.state.players],
        "hand": [player.hand_size for player in game.state.players],
        "items": [player.treasure_count for player in game.state.players],
        "names": [player.name for player in game.state.players],
    }


def _what_changed(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    card: str,
) -> list[dict[str, Any]]:
    """
    Say what moved, in sentences rather than numbers.

    Nothing moving is an answer too, and a common one for a card whose first
    version does nothing — so it is said out loud rather than left as an empty
    list somebody has to interpret.
    """
    said: list[dict[str, Any]] = []
    words = {
        "coins": "¢",
        "hp": " health",
        "hand": " cards in hand",
        "items": " items",
    }

    for seat, who in enumerate(after["names"]):
        for field, noun in words.items():
            was, now = before[field][seat], after[field][seat]

            if was == now:
                continue

            direction = "gained" if now > was else "lost"

            said.append(
                {
                    "who": who,
                    "what": f"{who} {direction} {abs(now - was)}{noun}"
                    f" ({was} → {now})",
                }
            )

    if not said:
        said.append(
            {
                "who": "",
                "what": f"{card} was played and nothing changed. That may be "
                f"right — some cards only matter later, or need something on "
                f"the table that was not there.",
            }
        )

    return said
