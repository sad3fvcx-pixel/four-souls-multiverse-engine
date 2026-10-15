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

The game being watched is dealt from a library read when the desk started, and
the desk is where an author writes new cards while it runs. So the desk keeps
the library as well as the session: when the author's own sets have changed on
disk it reads them again, and a game dealt after that is dealt from what is
there now. A session is never told to read anything — it is replaced by a new
one built from the new library, which is a thing ``Session`` already does.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fsme.api import Session
from fsme.content import ContentLibrary
from fsme.content.workspace import SETS, home, identifier_for
from fsme.scenario import Scenario
from fsme.util.errors import EngineError
from fsme.web.server import HTML, JSON, GameHandler, GameServer
from fsme.web.server import STATIC as GAME_STATIC

from . import author, games
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

        if path == "/api/suggestions":
            # The words already written, which are content and not capability:
            # `/api/capabilities` says what the engine can do and would say the
            # same thing with no cards loaded at all. This says what has been
            # called what, and changes every time somebody saves a card.
            self._json({"pools": author.suggestions(self.bench.root)})

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

            # The same disagreement the report path below explains at length:
            # `isdigit` admits `"²"` and a number of more than four thousand
            # three hundred digits, and `int` refuses both. Asking only the
            # first let them through to kill the handler, which then answers a
            # closed socket and no status — worse than the refusal this path
            # already has for a name that is not a number. `isdigit` stays for
            # the reason it stays there: `int` alone would newly accept `-1`,
            # `+1` and `1_0`, and the last of those is ten.
            try:
                number = int(wanted) if wanted.isdigit() else None
            except ValueError:
                number = None

            job = self.bench.job(number) if number is not None else None

            if job is None:
                self._json({"error": "no such job"}, status=404)
            else:
                self._json(job.to_dict())

            return

        if path == "/api/cards":
            if self.desk.library is None:
                self._json({"cards": self.bench.cards()})

                return

            # The cards to choose a test from are the ones the desk would deal
            # now, which a set written since the page opened can change.
            with self.lock:
                try:
                    self.desk.library_now()
                except EngineError as refused:
                    self._json({"error": str(refused)}, status=400)

                    return

                self._json({"cards": self.bench.cards()})

            return

        if path.startswith("/api/report/"):
            wanted = path.rsplit("/", 1)[-1]

            # `isdigit` and `int` disagree about what a number is, and both
            # halves of the disagreement arrive over HTTP. `"²".isdigit()` is
            # true and `int("²")` raises; so does a number of more than four
            # thousand three hundred digits, which `int` refuses by length.
            # Asking either question alone let the other through to kill the
            # handler, and a dead handler answers nothing at all — the socket
            # closes with no status, which is worse than the plain refusal
            # this path already has for a name that is not a number.
            #
            # The condition asks `isdigit` first and keeps it. Not redundant:
            # it is what says a job is named by digits, and `int` alone would
            # newly accept `-1`, `+1` and `1_0` — the last of which is ten, so
            # a report would be served under a name nobody asked for.
            try:
                number = int(wanted) if wanted.isdigit() else None
            except ValueError:
                number = None

            bundle = (
                self.bench.bundle(number) if number is not None else None
            )

            if bundle is None:
                self._json({"error": "no saved report for that job"}, status=404)

                return

            body = json.dumps(bundle).encode("utf-8")

            # From the number, not from what was typed. The two differ only in
            # leading zeros, which no page produces — `watching` is a job's own
            # integer id — and a header built from an integer cannot carry a
            # quote, a semicolon or a line ending whatever arrives here later.
            name = f"fsme-report-{number}.json"

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

        if self.desk.library is not None and path in (
            "/api/content",
            "/api/games",
            "/api/games/catalogue",
        ):
            with self.lock:
                try:
                    loaded = self.desk.library_now()
                except EngineError as refused:
                    # A set somebody edited by hand into something that does
                    # not load. The game being watched is untouched.
                    self._json({"error": str(refused)}, status=400)

                    return

                self._json(self._about_games(path, loaded))

            return

        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802 - the base class names it
        """
        Answer whether a path exists without doing it.

        The watch page asks about ``/api/autoplay`` to decide whether to show
        the button at all: the plain game server has no bot in it, and a button
        that produced a 404 would be a lie about what this build can do. It
        asks about ``/api/games`` the same way before showing custom games,
        which need a library to deal them from.
        """
        path = self.path.split("?", 1)[0]

        offered = path == "/api/autoplay" or (
            path == "/api/games" and self.desk.library is not None
        )

        self.send_response(200 if offered else 404)
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
                    "/api/cards/delete", "/api/cards/open",
                    "/api/cards/try"):
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

        if self.desk.library is not None and path in (
            "/api/restart",
            "/api/games/save",
            "/api/games/delete",
            "/api/games/start",
            "/api/games/leave",
        ):
            try:
                body = self._body()
            except ValueError as error:
                self._json({"error": str(error)}, status=400)

                return

            with self.lock:
                try:
                    answer = self._games(path, body)
                except games.GameError as complaint:
                    self._json(
                        {"error": str(complaint), "problems": complaint.problems},
                        status=400,
                    )

                    return
                except (ValueError, EngineError) as refused:
                    # A set that is not loaded, a character the deal cannot
                    # find, a number of players nobody can seat. All of them are
                    # answers to what was asked, and the game being watched is
                    # still the one it was: nothing is replaced until the new
                    # one has been dealt.
                    self._json({"error": str(refused)}, status=400)

                    return

            self._json(answer)

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

        if self.desk.library is not None and body.get("kind") == "test-card":
            # A card is looked up when its test starts, so the library is
            # brought up to date first: a card written since the list was last
            # asked for would otherwise be unknown to the job testing it.
            with self.lock:
                try:
                    self.desk.library_now()
                except EngineError as refused:
                    self._json({"error": str(refused)}, status=400)

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
            saved = author.save_card(body)
            saved["problems"] = author.in_plain_words(saved["problems"])

            return saved

        if path == "/api/cards/check":
            card = author.build_card(body)

            return {
                "card": card,
                "problems": author.in_plain_words(author.check_card(card)),
            }

        if path == "/api/cards/delete":
            author.delete_card(str(body.get("set", "")), str(body.get("card", "")))

            return {"deleted": True}

        if path == "/api/cards/open":
            # A card that cannot be read faithfully is not opened at all. The
            # reason travels as itself rather than as a failure, because it is
            # something to show a person and not something that went wrong.
            try:
                return author.open_card(
                    str(body.get("set", "")), str(body.get("card", ""))
                )
            except author.UnreadableCard as why:
                return {"unreadable": str(why)}

        card = author.build_card(body)
        problems = author.check_card(card)

        if problems:
            return {"problems": author.in_plain_words(problems), "moments": []}

        try:
            return {"problems": [], "moments": self.bench.show_card(card)}
        except EngineError as refused:
            # The engine would not play it. That is an answer to "try it in a
            # game" and not a failure of the request: a card can be well formed
            # and still be one the engine stops on, and somebody who pressed a
            # button has to be told which. Letting this out of the handler
            # killed the connection and left the page silent.
            return {
                "problems": [author.said_by_the_engine(refused)],
                "moments": [],
            }

    def _about_games(self, path: str, loaded: ContentLibrary) -> dict[str, Any]:
        """
        What the watch page reads about content and custom games, from the
        library as it is now rather than as it was when the desk started.
        """
        if path == "/api/content":
            # The same answer the game server gives, read off the current
            # library: a set made a minute ago is offered, and choosing it
            # deals a new game from the library that holds it.
            return {
                "sets": [
                    {"id": one.id, "name": one.manifest.name, "cards": len(one)}
                    for one in sorted(loaded, key=lambda one: one.id)
                ],
                "chosen": list(self.session.chosen),
            }

        if path == "/api/games/catalogue":
            return games.catalogue(loaded)

        return {
            "games": games.list_games(loaded),
            "where": str(games.games_directory()),
            "active": self.desk.active,
        }

    def _games(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """
        Deal, keep and throw away custom games, and deal ordinary games again.

        Every path that deals builds a whole new session and only then puts it
        in place of the old one, so a deal the engine refuses leaves the game
        being watched exactly where it was.
        """
        desk = self.desk

        if path == "/api/games/save":
            saved = games.save_game(body.get("game"), replace=body.get("replace") is True)

            return {"saved": True, **saved}

        if path == "/api/games/delete":
            games.delete_game(str(body.get("id") or ""))

            return {"deleted": True}

        current = self.session
        seed = _given(body.get("seed"), "the seed")

        if path == "/api/games/start":
            scenario = games.load_game(str(body.get("id") or ""))
            problems = games.availability(scenario, desk.library_now())

            if problems:
                raise games.GameError(problems[0], problems)

            if seed is None:
                seed = scenario.seed if scenario.seed is not None else 0

            dealt = desk.deal(scenario=scenario, seed=seed)
            desk.active = {
                "id": identifier_for(str(body.get("id"))),
                "name": scenario.name,
            }

            return {"view": dealt.view(0), "active": desk.active}

        if seed is None:
            seed = current.game.state.seed

        if (
            path == "/api/restart"
            and desk.active is not None
            and current.scenario is not None
        ):
            # Dealing a custom game again is dealing the same game from another
            # seed. The chairs and the sets are the game's own, so what the page
            # sends for those is not applied on top of it.
            dealt = desk.deal(scenario=current.scenario, seed=seed)

            return {"view": dealt.view(0)}

        players = _given(body.get("players"), "the number of players")
        sets = body.get("sets")

        if sets is not None and not isinstance(sets, list):
            raise ValueError("the sets are a list")

        if path == "/api/games/leave":
            players = players if players is not None else desk.players
            sets = sets if sets is not None else []
        else:
            players = players if players is not None else len(current.game.state.players)
            sets = sets if sets is not None else list(current.chosen)

        dealt = desk.deal(scenario=None, seed=seed, players=players, sets=sets)
        desk.active = None

        return {"view": dealt.view(0)}

    def _json(self, payload: Any, status: int = 200) -> None:
        self._send(JSON, json.dumps(payload).encode("utf-8"), status=status)


class DeskServer(GameServer):
    """
    The game server, with somewhere to put work beside it.

    ``library`` and ``reload`` are what lets the game being watched include
    cards written since the desk started: the library the session was dealt
    from, and how to read it again. A desk built without them deals from the
    session it was handed and offers no custom games, which is what it did
    before either existed.
    """

    def __init__(
        self,
        address: tuple[str, int],
        session: Session,
        bench: Workbench,
        *,
        library: ContentLibrary | None = None,
        reload: Callable[[], ContentLibrary] | None = None,
        interactive_priority: bool = True,
        players: int = 2,
    ) -> None:
        super().__init__(address, session)

        # The base class picked the game handler; the desk needs its own.
        self.RequestHandlerClass = DeskHandler

        self.bench = bench

        self.library = library
        self.reload = reload
        self.interactive_priority = interactive_priority
        self.players = players

        self.active: dict[str, str] | None = None
        """The custom game being watched, by id and name, or None."""

        self._seen = _fingerprint(home() / SETS)

    def library_now(self) -> ContentLibrary:
        """
        The library to deal from, read again if the author's sets changed.

        Only the author's own sets are watched: they are the ones written while
        the desk runs. The cards FSME ships are read again only when the desk
        is started again, as they always were. Reading every set is not cheap,
        so it happens when something on disk moved and not on every request.
        Called with the server's lock held.
        """
        if self.library is None:
            raise ValueError("this desk has no library to deal custom games from")

        if self.reload is None:
            return self.library

        seen = _fingerprint(home() / SETS)

        if seen != self._seen:
            # Read first and remember after: a set that will not load leaves
            # the library as it was, and is reported again on the next request
            # rather than forgotten. The bench is handed the same library, so
            # the cards it offers and tests are the ones dealt here; a set that
            # will not load leaves both as they were.
            self.library = self.reload()
            self.bench.use(self.library)
            self._seen = seen

        return self.library

    def deal(
        self,
        *,
        scenario: Scenario | None,
        seed: int,
        players: int | None = None,
        sets: list[Any] | None = None,
    ) -> Session:
        """
        Deal a new game from the current library and make it the one watched.

        A custom game seats as many players as it has chairs and deals from its
        own sets; an ordinary one takes both from the page. Nothing replaces
        the game being watched until the new one has been dealt.
        """
        loaded = self.library_now()

        if scenario is not None:
            dealt = Session(
                loaded,
                players=len(scenario.players) or self.players,
                seed=seed,
                interactive_priority=self.interactive_priority,
                scenario=scenario,
            )
        else:
            dealt = Session(
                loaded,
                players=players if players is not None else self.players,
                seed=seed,
                interactive_priority=self.interactive_priority,
            )

            if sets:
                dealt.restart(sets=[str(one) for one in sets])

        self.session = dealt

        return dealt


def _whose_move(game: Any) -> int:
    """
    Whose turn it is to say something.
    """
    from fsme.lab.simulation.runner import _whose_move as asked

    return int(asked(game))


def _fingerprint(directory: Path) -> tuple[tuple[str, int, int, int], ...]:
    """
    Every file under a directory, with what changes when it is written.

    Path, size, inode and modification time. A card is saved by writing a file
    beside itself and moving it into place, so even a save of the same size at
    the same instant is a new inode. Files whose names start with a dot are the
    half-written ones that move is made from, and are not content.
    """
    if not directory.is_dir():
        return ()

    found: list[tuple[str, int, int, int]] = []

    for root, folders, files in os.walk(directory):
        folders[:] = sorted(one for one in folders if not one.startswith("."))

        for name in sorted(files):
            if name.startswith("."):
                continue

            path = Path(root) / name

            try:
                facts = path.stat()
            except OSError:
                continue

            found.append(
                (
                    str(path.relative_to(directory)),
                    facts.st_size,
                    facts.st_ino,
                    facts.st_mtime_ns,
                )
            )

    return tuple(found)


def _given(value: Any, what: str) -> int | None:
    """
    A whole number from a page, or None when it was not sent.

    Read the way the game server reads a seed — any whole number — but refused
    out loud when it is not one, instead of failing somewhere further in.
    """
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        raise ValueError(f"{what} is a whole number, not {value!r}")

    if isinstance(value, int):
        return value

    if isinstance(value, float) and value.is_integer():
        return int(value)

    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            pass

    raise ValueError(f"{what} is a whole number, not {value!r}")


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
    *,
    library: ContentLibrary | None = None,
    reload: Callable[[], ContentLibrary] | None = None,
    interactive_priority: bool = True,
    players: int = 2,
) -> DeskServer:
    """
    Build the desk. The caller decides when to start serving.

    ``library`` is what ``session`` was dealt from and ``reload`` reads it
    again; with both, a set written while the desk runs can be watched without
    starting it again, and custom games are offered.
    """
    return DeskServer(
        (host, port),
        session,
        bench,
        library=library,
        reload=reload,
        interactive_priority=interactive_priority,
        players=players,
    )
