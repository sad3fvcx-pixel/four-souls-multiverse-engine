# src/fsme/lab/desk/server.py

"""
A front door for the whole thing.

Everything FSME can do is behind a command with flags, which is fine for the
person who wrote them and no use to anybody else. This puts the four things
worth doing on one page: play a game, run a study, test a card, open a report.

It is built *on top of* the game server rather than beside it. The desk extends
``fsme.web.GameServer``, so the game page and its endpoints work exactly as
they did and the desk adds paths of its own — which also keeps the dependency
pointing the right way. The core web server has never heard of the laboratory;
this is the laboratory reaching down to the core, which is the direction
allowed.

Long work does not happen in a request. A study is started, and the page asks
how it is going until it is done — see ``bench``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fsme.api import Session
from fsme.web.server import HTML, JSON, GameHandler, GameServer
from fsme.web.server import STATIC as GAME_STATIC

from . import author
from .bench import Workbench
from .capabilities import catalogue

STATIC = Path(__file__).resolve().parent / "static"

MOST_GAMES = 5000
"""
The largest run the page will start.

Not a rule of the engine, a courtesy to whoever clicked: a typed digit too many
in a box is an easy mistake, and an afternoon of accidental simulation is not
an easy one to notice.
"""


class DeskHandler(GameHandler):
    """
    The game handler, plus the paths the desk needs.
    """

    @property
    def desk(self) -> DeskServer:
        server: DeskServer = self.server  # type: ignore[assignment]

        return server

    @property
    def bench(self) -> Workbench:
        return self.desk.bench

    def do_GET(self) -> None:  # noqa: N802 - the base class names it
        path = self.path.split("?", 1)[0]

        if path in ("/", "/index.html"):
            # What a person came to do. The engine's own four things are still
            # here, one click away, under "Everything else".
            self._send(HTML, (STATIC / "author.html").read_bytes())

            return

        if path in ("/advanced", "/desk"):
            self._send(HTML, (STATIC / "desk.html").read_bytes())

            return

        if path == "/api/capabilities":
            # Everything the engine can do, with the words already on it, so
            # that a page never has to keep a list of its own.
            self._json(catalogue())

            return

        if path == "/api/sets":
            self._json({"sets": author.sets(), "where": str(author.sets_directory())})

            return

        if path == "/play":
            # The game itself, still served by the core's own page.
            self._send(HTML, (GAME_STATIC / "index.html").read_bytes())

            return

        if path == "/api/jobs":
            self._json({"jobs": [job.to_dict() for job in self.bench.jobs()]})

            return

        if path.startswith("/api/jobs/"):
            wanted = path.rsplit("/", 1)[-1]

            job = self.bench.job(int(wanted)) if wanted.isdigit() else None

            if job is None:
                self._json({"error": "no such job"}, status=404)
            else:
                self._json(job.to_dict())

            return

        if path == "/api/cards":
            self._json({"cards": self.bench.cards()})

            return

        if path.startswith("/api/report/"):
            wanted = path.rsplit("/", 1)[-1]

            bundle = (
                self.bench.bundle(int(wanted)) if wanted.isdigit() else None
            )

            if bundle is None:
                self._json({"error": "no saved report for that job"}, status=404)

                return

            body = json.dumps(bundle).encode("utf-8")
            name = f"fsme-report-{wanted}.json"

            self.send_response(200)
            self.send_header("Content-Type", JSON)
            self.send_header("Content-Length", str(len(body)))
            self.send_header(
                "Content-Disposition", f'attachment; filename="{name}"'
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

            return

        if path == "/api/journals":
            self._json({"journals": self.bench.journals()})

            return

        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802 - the base class names it
        """
        Answer whether a path exists without doing it.

        The watch page asks about ``/api/autoplay`` to decide whether to show
        the button at all: the plain game server has no bot in it, and a button
        that produced a 404 would be a lie about what this build can do.
        """
        path = self.path.split("?", 1)[0]

        self.send_response(200 if path == "/api/autoplay" else 404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802 - the base class names it
        path = self.path.split("?", 1)[0]

        if path == "/api/autoplay":
            try:
                body = self._body()
            except ValueError as error:
                self._json({"error": str(error)}, status=400)

                return

            with self.lock:
                self._json(
                    self._autoplay(
                        _within(body.get("moves"), 8, low=1, high=64),
                        since=self._since(),
                    )
                )

            return

        if path in ("/api/sets/new", "/api/sets/delete",
                    "/api/cards/save", "/api/cards/check",
                    "/api/cards/delete", "/api/cards/try"):
            try:
                body = self._body()
            except ValueError as error:
                self._json({"error": str(error)}, status=400)

                return

            try:
                self._json(self._author(path, body))
            except author.AuthorError as complaint:
                # Something the person did, said in words meant for them.
                self._json({"error": str(complaint)}, status=400)

            return

        if path == "/api/load":
            try:
                body = self._body()
            except ValueError as error:
                self._json({"error": str(error)}, status=400)

                return

            try:
                job = self.bench.take_bundle(body)
            except ValueError as error:
                self._json({"error": str(error)}, status=400)

                return

            self._json(job.to_dict())

            return

        if path != "/api/run":
            super().do_POST()

            return

        try:
            body = self._body()
        except ValueError as error:
            self._json({"error": str(error)}, status=400)

            return

        try:
            job = self._run(body)
        except ValueError as error:
            self._json({"error": str(error)}, status=400)

            return

        self._json(job.to_dict())

    def _autoplay(self, moves: int, *, since: int = 0) -> dict[str, Any]:
        """
        Let the bot take a few moves in the game the page is watching.

        A few rather than all of them: the page redraws between batches, so a
        game plays out visibly instead of finishing in one request and looking
        like nothing happened.

        ``since`` is where the page has read up to, and it is answered the same
        way ``/api/command`` answers it. Sending the whole history back after
        every batch made the account of the game repeat itself: a watcher saw
        each sentence again for every batch that followed it, so a game of
        three hundred moves read as two thousand lines.

        The bot lives in the laboratory and the game server is core, which is
        why this is here rather than in ``fsme.web`` — the core has never heard
        of the bot and this keeps it that way.

        Every move goes in through ``Session.submit`` rather than straight into
        the game. That is what puts it in the journal: the bot used to play past
        the recorder, so the mode most likely to be watched was the one mode
        that left no record of itself.
        """
        from fsme.lab.bot import HeuristicBot
        from fsme.lab.simulation import ScriptedAgent

        session = self.session
        game = session.game

        bot = HeuristicBot(seed=len(game.history))
        agent = ScriptedAgent(seed=len(game.history))

        moved = 0

        for _ in range(moves):
            if game.is_over:
                break

            decision = game.runtime.awaiting_decision

            if decision is not None:
                # The bot has no opinion about most questions and says so; the
                # scripted agent answers them the same way a simulation does.
                chosen = agent.choose(game)

                if chosen is None:
                    break

                command, label = chosen
            else:
                seat = _whose_move(game)
                thought = bot.choose(game, seats=(seat,))

                if thought is None:
                    break

                command, label = thought[0], thought[1]

            outcome = session.submit(
                {
                    "type": str(command.type),
                    "player": command.player,
                    "payload": dict(command.payload),
                    "label": label,
                }
            )

            if not outcome["accepted"]:
                break

            moved += 1

        return {
            "moved": moved,
            "over": bool(game.is_over),
            "view": session.view(since),
        }

    def _run(self, body: dict[str, Any]) -> Any:
        """
        Start whichever of the four was asked for.
        """
        kind = str(body.get("kind") or "")

        players = _within(body.get("players"), 2, low=1, high=4)
        games = _within(body.get("games"), 100, low=1, high=MOST_GAMES)
        jobs = _within(body.get("jobs"), 1, low=1, high=16)
        seed = _within(body.get("seed"), 1, low=0, high=2**31 - 1)

        seats = tuple(
            int(seat)
            for seat in body.get("bot_seats") or ()
            if str(seat).isdigit() and int(seat) < players
        )

        if kind == "play":
            return self.bench.play(seed, players, seats)

        if kind == "study":
            return self.bench.study(games, players, jobs, seats)

        if kind == "test-card":
            card = str(body.get("card") or "").strip()

            if not card:
                raise ValueError("name a card to test")

            return self.bench.test_card(card, games, players, jobs)

        if kind == "report":
            name = str(body.get("name") or "").strip()

            if not name:
                raise ValueError("name a game to report on")

            return self.bench.open_report(name)

        raise ValueError(f"nothing here does {kind!r}")

    def _author(self, path: str, body: Any) -> Any:
        """
        The authoring calls, which all take what a person filled in.
        """
        if path == "/api/sets/new":
            return author.make_set(str(body.get("name", "")))

        if path == "/api/sets/delete":
            author.delete_set(str(body.get("set", "")))

            return {"deleted": True}

        if path == "/api/cards/save":
            return author.save_card(body)

        if path == "/api/cards/check":
            card = author.build_card(body)

            return {"card": card, "problems": author.check_card(card)}

        if path == "/api/cards/delete":
            author.delete_card(str(body.get("set", "")), str(body.get("card", "")))

            return {"deleted": True}

        card = author.build_card(body)
        problems = author.check_card(card)

        if problems:
            return {"problems": problems, "moments": []}

        return {"problems": [], "moments": self.bench.show_card(card)}

    def _json(self, payload: Any, status: int = 200) -> None:
        self._send(JSON, json.dumps(payload).encode("utf-8"), status=status)


class DeskServer(GameServer):
    """
    The game server, with somewhere to put work beside it.
    """

    def __init__(
        self, address: tuple[str, int], session: Session, bench: Workbench
    ) -> None:
        super().__init__(address, session)

        # The base class picked the game handler; the desk needs its own.
        self.RequestHandlerClass = DeskHandler

        self.bench = bench


def _whose_move(game: Any) -> int:
    """
    Whose turn it is to say something.
    """
    from fsme.lab.simulation.runner import _whose_move as asked

    return int(asked(game))


def _within(given: Any, fallback: int, *, low: int, high: int) -> int:
    """
    Read a number from a browser, and keep it inside what makes sense.
    """
    try:
        value = int(given)
    except (TypeError, ValueError):
        return fallback

    return max(low, min(high, value))


def desk(
    session: Session,
    bench: Workbench,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> DeskServer:
    """
    Build the desk. The caller decides when to start serving.
    """
    return DeskServer((host, port), session, bench)
