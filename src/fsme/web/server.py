# src/fsme/web/server.py

"""
A small HTTP server that puts one game in a browser.

It is a client of the engine and nothing else: it serves a page, hands that
page the view the API produces, and posts back whatever the page says the
player did. No rule is decided here — the page cannot ask this server anything
the engine would not answer the same way.

The standard library is the whole of it, on purpose. The engine has no
dependencies, and neither should looking at it: a single file bundled by
PyInstaller must run on a machine with nothing installed.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from fsme.api import Session
from fsme.journal import Journal, JournalFormatError, suggested_name, unwrap, wrap
from fsme.narration import told
from fsme.util.errors import EngineError

STATIC = Path(__file__).resolve().parent / "static"

JSON = "application/json; charset=utf-8"
HTML = "text/html; charset=utf-8"


class GameHandler(BaseHTTPRequestHandler):
    """
    One request. The session it talks to belongs to the server.
    """

    server_version = "fsme"

    protocol_version = "HTTP/1.1"
    """
    Keep-alive, so a page polling three times a second is not three
    connections a second.
    """

    @property
    def game_server(self) -> GameServer:
        """
        The server this request belongs to, which is where the game lives.
        """
        server: GameServer = self.server  # type: ignore[assignment]

        return server

    @property
    def session(self) -> Session:
        return self.game_server.session

    @property
    def lock(self) -> threading.Lock:
        return self.game_server.lock

    def log_message(self, format: str, *args: Any) -> None:
        """
        Say nothing. A game is not a web log.
        """

    def do_GET(self) -> None:  # noqa: N802 - the base class names it
        path = self.path.split("?", 1)[0]

        if path in ("/", "/index.html"):
            self._send(HTML, (STATIC / "index.html").read_bytes())

            return

        if path == "/favicon.ico":
            # Asked for by every browser and served by nobody: an empty answer
            # is quieter than a 404 in the console.
            self._send("image/x-icon", b"", status=204)

            return

        if path == "/api/view":
            since = self._since()

            with self.lock:
                self._json(self.session.view(since))

            return

        if path == "/api/content":
            # Which sets this game can be dealt from, and which of them it is
            # being dealt from now. A set somebody wrote is here on exactly the
            # same terms as one FSME ships, because both were loaded by the
            # same loader into the same library.
            with self.lock:
                self._json(
                    {
                        "sets": [
                            {
                                "id": one.id,
                                "name": one.manifest.name,
                                "cards": len(one),
                            }
                            for one in self.session.sets
                        ],
                        "chosen": list(self.session.chosen),
                    }
                )

            return

        if path == "/api/save":
            with self.lock:
                self._json(self.session.save())

            return

        if path == "/api/journal":
            since = self._since()

            with self.lock:
                self._json(self._journal(since))

            return

        if path == "/api/journal/file":
            # The whole journal, as a file to keep. Not the paged view: a save
            # is not a poll, and `total` is a paging aid rather than part of
            # the game.
            with self.lock:
                journal = self.session.journal
                body = json.dumps(wrap(journal)).encode("utf-8")
                name = suggested_name(journal)

            self._send(
                JSON,
                body,
                headers={"Content-Disposition": f'attachment; filename="{name}"'},
            )

            return

        self._send(HTML, b"not here", status=404)

    def do_POST(self) -> None:  # noqa: N802 - the base class names it
        path = self.path.split("?", 1)[0]

        try:
            body = self._body()
        except ValueError as error:
            self._json({"error": str(error)}, status=400)

            return

        if path == "/api/command":
            with self.lock:
                try:
                    outcome = self.session.submit(body)
                except (ValueError, EngineError) as error:
                    # A set that was never loaded, a number of players nobody
                    # can deal, or a choice of sets no game can be made from.
                    # All three are answers to what was asked rather than
                    # faults, and the session is left as it was.
                    self._json({"error": str(error)}, status=400)

                    return

                answer = dict(outcome)
                answer["view"] = self.session.view(self._since())

            self._json(answer)

            return

        if path == "/api/journal/open":
            # Read a saved journal and hand it back with its account, without
            # touching the game. Nothing here starts, continues or replaces a
            # session: opening a saved game is reading, and the game being
            # watched is still where it was.
            #
            # The checking happens here rather than in the page so that there
            # is one implementation of what a journal file is, and so that the
            # sentences a user reads when a file is wrong are the ones the
            # tests read too.
            try:
                journal = unwrap(body.get("file"))
            except JournalFormatError as error:
                self._json({"error": str(error)}, status=400)

                return

            self._json(
                {
                    "journal": journal.to_dict(),
                    "account": _account(journal),
                }
            )

            return

        if path == "/api/restart":
            with self.lock:
                try:
                    self.session.restart(
                        seed=body.get("seed"),
                        players=body.get("players"),
                        sets=body.get("sets"),
                    )
                except ValueError as error:
                    self._json({"error": str(error)}, status=400)

                    return

                self._json({"view": self.session.view(0)})

            return

        self._json({"error": "no such endpoint"}, status=404)

    def _journal(self, since: int) -> dict[str, Any]:
        """
        The journal, or the part of it the caller has not seen.

        ``since`` is an entry index, so a page showing a long game asks for the
        moves it is missing rather than the whole game after every click. The
        answer is otherwise exactly what the journal writes to a file — the same
        dictionary, the same keys — because the journal is the record and this
        endpoint is a window onto it, not a second version of it.

        ``total`` is how many entries the journal holds regardless of the slice,
        which is what a caller polls to know whether it is behind.
        """
        journal = self.session.journal

        written = journal.to_dict()
        written["entries"] = written["entries"][max(0, since):]
        written["total"] = len(journal)

        return written

    def _since(self) -> int:
        _, _, query = self.path.partition("?")

        for part in query.split("&"):
            key, _, value = part.partition("=")

            if key == "since" and value.isdigit():
                return int(value)

        return 0

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)

        if not length:
            return {}

        raw = self.rfile.read(length)

        try:
            body = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError(f"the request body is not JSON: {error}") from None

        if not isinstance(body, dict):
            raise ValueError("the request body must be an object")

        return body

    def _json(self, payload: Any, status: int = 200) -> None:
        self._send(JSON, json.dumps(payload).encode("utf-8"), status=status)

    def _send(
        self,
        kind: str,
        body: bytes,
        status: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")

        for name, value in (headers or {}).items():
            self.send_header(name, value)

        self.end_headers()
        self.wfile.write(body)


class GameServer(ThreadingHTTPServer):
    """
    An HTTP server with one game behind it.

    The lock is not decoration. A browser fires overlapping requests, and the
    engine is a single mutable game: two commands landing at once would
    interleave inside one command's resolution, which is exactly the thing the
    Runtime's single mutation point exists to prevent.
    """

    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], session: Session) -> None:
        super().__init__(address, GameHandler)

        self.session = session
        self.lock = threading.Lock()


def serve(session: Session, host: str = "127.0.0.1", port: int = 8000) -> GameServer:
    """
    Build the server. The caller decides when to start serving.
    """
    return GameServer((host, port), session)


def _account(journal: Journal) -> list[str]:
    """
    A saved game read out, in the words a live one is read out in.

    The same call ``fsme.api.view`` makes for a game in progress. That is not
    tidiness: ``narration`` exists on the rule that a live game and a saved
    journal are the same events and so get the same sentences, and two
    narrators would drift until nobody could say which account of a game was
    the right one.
    """
    names = dict(enumerate(journal.players))

    return [
        said
        for entry in journal.entries
        for said in (told(happening.to_dict(), names=names) for happening in entry.events)
        if said
    ]
