"""
The web layer.

It is a client of the engine, so what is worth testing is that it stays one: it
passes commands through, it hands back the view the API produced, and it refuses
anything malformed instead of letting it reach the game.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from fsme.api import Session, load_content
from fsme.content import ContentLibrary
from fsme.web import serve

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture
def address(everything: ContentLibrary):
    """
    A running server on a port the operating system picked.
    """
    server = serve(Session(everything, players=2, seed=7), host="127.0.0.1", port=0)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address[:2]

    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def get(address: str, path: str) -> Any:
    with urllib.request.urlopen(f"{address}{path}", timeout=10) as answer:
        return json.loads(answer.read())


def post(address: str, path: str, body: Any) -> Any:
    request = urllib.request.Request(
        f"{address}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=10) as answer:
        return json.loads(answer.read())


def test_the_page_is_served(address: str) -> None:
    with urllib.request.urlopen(f"{address}/", timeout=10) as answer:
        body = answer.read().decode()

    assert answer.status == 200
    assert "<title>FSME</title>" in body


def test_the_view_comes_back_as_data(address: str) -> None:
    view = get(address, "/api/view?since=0")

    assert view["state"]["started"] is True
    assert len(view["state"]["players"]) == 2
    assert isinstance(view["moves"], list)
    assert view["history_length"] == len(view["events"])


def test_a_command_is_passed_through_and_answered(address: str) -> None:
    view = get(address, "/api/view?since=0")

    move = next(move for move in view["moves"] if move["type"] == "pass_priority")

    answer = post(address, "/api/command?since=0", move)

    assert answer["accepted"] is True
    assert "view" in answer, "the answer carries the position the move produced"


def test_a_refused_command_comes_back_refused_not_broken(address: str) -> None:
    answer = post(
        address,
        "/api/command?since=0",
        {"type": "attack", "player": 0, "payload": {"index": 99}},
    )

    assert answer["accepted"] is False
    assert answer["reason"]


def test_a_command_the_engine_has_never_heard_of_is_a_bad_request(
    address: str,
) -> None:
    with pytest.raises(urllib.error.HTTPError) as raised:
        post(address, "/api/command", {"type": "flip_the_table", "player": 0})

    assert raised.value.code == 400


def test_a_body_that_is_not_json_is_a_bad_request(address: str) -> None:
    request = urllib.request.Request(
        f"{address}/api/command",
        data=b"not json at all",
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(request, timeout=10)

    assert raised.value.code == 400


def test_the_game_can_be_dealt_again_over_http(address: str) -> None:
    answer = post(address, "/api/restart", {"seed": 42, "players": 3})

    assert answer["view"]["state"]["seed"] == 42
    assert len(answer["view"]["state"]["players"]) == 3


def test_an_impossible_table_is_refused(address: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as raised:
        post(address, "/api/restart", {"players": 11})

    assert raised.value.code == 400


def test_a_game_can_be_saved_over_http(address: str) -> None:
    saved = get(address, "/api/save")

    assert saved["format"]
    assert saved["players"]


def test_anything_else_is_not_here(address: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as raised:
        get(address, "/api/whatever")

    assert raised.value.code == 404
