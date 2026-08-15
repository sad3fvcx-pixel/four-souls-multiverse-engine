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


def test_the_journal_of_the_browser_game_can_be_fetched(address: str) -> None:
    """
    A game played in a browser is a game somebody may want to read afterwards.
    """
    view = get(address, "/api/view?since=0")
    move = next(move for move in view["moves"] if move["type"] == "pass_priority")

    post(address, "/api/command?since=0", move)

    journal = get(address, "/api/journal")

    assert journal["format"]
    assert journal["seed"] == 7
    assert len(journal["entries"]) == 1
    assert journal["entries"][0]["label"] == move["label"]


def test_the_watch_page_reads_the_game_out(address: str) -> None:
    """
    What a person sees first has to be sentences, not event names.

    The page used to show only the technical log, so somebody watching could
    tell the engine was working and not what was happening in the game.
    """
    post(address, "/api/command", {"type": "start_game", "player": 0})

    events = get(address, "/api/view?since=0")["events"]

    assert events

    told = [one["said"] for one in events if one.get("said")]

    assert told, "nothing was said about a game that started"
    assert any("turn begins" in line for line in told)

    # And the technical log is still all of it, kept as the wider view.
    assert len(told) < len(events)


def test_the_page_leads_with_the_account_and_keeps_the_log(address: str) -> None:
    with urllib.request.urlopen(f"{address}/", timeout=10) as answer:
        home = answer.read().decode("utf-8")

    assert "What is happening" in home
    assert "Every event" in home

    # A seed nobody has to invent, and one they can keep.
    assert 'id="roll-seed"' in home
    assert 'id="copy-seed"' in home

    # A card shows what it says.
    assert "data-text=" in home


def test_the_plain_server_does_not_offer_a_bot_it_does_not_have(
    address: str,
) -> None:
    """
    The core game server has never heard of the laboratory.

    The button asks before showing itself, so a build without a bot says so
    with a 404 rather than offering something that cannot happen.
    """
    request = urllib.request.Request(f"{address}/api/autoplay", method="HEAD")

    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            assert answer.status != 200
    except urllib.error.HTTPError as refused:
        assert refused.code in (404, 501)
