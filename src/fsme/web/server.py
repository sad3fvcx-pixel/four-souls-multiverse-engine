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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from fsme.api import Session

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

        if path == "/api/save":
            with self.lock:
                self._json(self.session.save())

            return

        if path == "/api/journal":
            since = self._since()

            with self.lock:
                self._json(self._journal(since))

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
                except ValueError as error:
                    self._json({"error": str(error)}, status=400)

                    return

                answer = dict(outcome)
                answer["view"] = self.session.view(self._since())

            self._json(answer)

            return

        if path == "/api/restart":
            with self.lock:
                try:
                    self.session.restart(
                        seed=body.get("seed"), players=body.get("players")
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

    def _send(self, kind: str, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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
