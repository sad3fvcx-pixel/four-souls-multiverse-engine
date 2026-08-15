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

from .bench import Workbench

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
            self._send(HTML, (STATIC / "desk.html").read_bytes())

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

    def do_POST(self) -> None:  # noqa: N802 - the base class names it
        path = self.path.split("?", 1)[0]

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
