"""
The web layer.

It is a client of the engine, so what is worth testing is that it stays one: it
passes commands through, it hands back the view the API produced, and it refuses
anything malformed instead of letting it reach the game.
"""

from __future__ import annotations

import json
import socket
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


def asked(address: str, target: str) -> tuple[int, bytes]:
    """
    One GET with the target put on the wire exactly as written.

    ``urllib`` and ``http.client`` both encode a request line as ASCII and
    raise on a path they cannot, so neither can ask about a superscript two —
    which is one latin-1 byte, which ``str.isdigit`` accepts, and which is
    therefore a question worth being able to ask.

    A status of nought means the handler answered with a closed socket and no
    status at all. That is what dying looks like from the outside.
    """
    host, _, port = address.removeprefix("http://").partition(":")

    with socket.create_connection((host, int(port)), timeout=10) as sock:
        sock.sendall(
            f"GET {target} HTTP/1.1\r\n".encode("latin-1")
            + b"Host: fsme\r\nConnection: close\r\n\r\n"
        )

        answer = b""

        while True:
            got = sock.recv(65536)

            if not got:
                break

            answer += got

    if not answer:
        return 0, b""

    head, _, body = answer.partition(b"\r\n\r\n")

    return int(head.split()[1]), body


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
    assert journal["entries"][-1]["label"] == move["label"]


def test_the_journal_begins_at_the_deal(address: str) -> None:
    """
    The opening hands, the starting cents and the first loot are moves too.

    They used to be missing. The journal was started after the game was dealt,
    so a record of the game began at the second thing that happened in it — and
    a reader looking for where three cents came from would find nothing.
    """
    journal = get(address, "/api/journal")

    assert journal["entries"], "the journal was empty before anybody had moved"

    opening = journal["entries"][0]

    assert opening["command"] == "start_game"
    assert opening["index"] == 0
    assert opening["events"], "the deal happened and nothing was written down"


def test_the_journal_can_be_asked_for_only_what_is_new(address: str) -> None:
    """
    A page showing a long game asks for the moves it is missing.

    Without this the watch page would re-fetch the whole game after every
    click, which is the kind of cost that only shows up in the games worth
    watching.
    """
    whole = get(address, "/api/journal")
    already = len(whole["entries"])

    view = get(address, "/api/view?since=0")
    move = next(move for move in view["moves"] if move["type"] == "pass_priority")

    post(address, "/api/command?since=0", move)

    rest = get(address, f"/api/journal?since={already}")

    assert len(rest["entries"]) == 1
    assert rest["entries"][0]["index"] == already
    assert rest["total"] == already + 1, "and it says how far behind the caller is"

    # The slice is a window onto the journal, not a different document: what it
    # says about the game is what the whole journal says.
    assert rest["seed"] == whole["seed"]
    assert rest["format"] == whole["format"]
    assert rest["players"] == whole["players"]


def test_a_since_too_long_to_be_a_number_is_read_as_the_beginning(
    address: str,
) -> None:
    """
    ``isdigit`` says yes and ``int`` says no, and the hint has to survive it.

    Python will not read an integer of more than four thousand three hundred
    digits out of a string, so such a query passed the guard and raised inside
    it. Nothing caught it, so the handler died and answered a closed socket
    with no status — where the contract here has always been that a hint this
    cannot read means "from the beginning".
    """
    status, body = asked(address, "/api/journal?since=" + "1" * 4301)

    assert status == 200, "the handler stopped instead of starting over"
    assert json.loads(body) == get(address, "/api/journal?since=0")


def test_a_since_that_is_a_digit_but_not_a_number_is_read_as_the_beginning(
    address: str,
) -> None:
    """
    A superscript two is a digit to ``str.isdigit`` and not one to ``int``.

    One latin-1 byte, so it reaches the handler exactly as sent. Asked over a
    socket because ``urllib`` encodes a request line as ASCII and will not send
    it at all.
    """
    from_nought = get(address, "/api/journal?since=0")

    for digit in ("²", "³", "¹"):
        status, body = asked(address, f"/api/journal?since={digit}")

        assert status == 200, f"{digit!r} stopped the handler"
        assert json.loads(body) == from_nought


def test_a_since_that_is_a_word_still_means_the_beginning(address: str) -> None:
    """
    The contract that was always here, and the one the fix above matches.
    """
    assert get(address, "/api/journal?since=abc") == get(
        address, "/api/journal?since=0"
    )


def test_the_mended_helper_is_the_one_every_route_reads(address: str) -> None:
    """
    `_since` is read by four callers, so the fix belongs to all of them.

    `/api/view` is the other reader a page hits on every poll; it died on the
    same query and must now answer the same as `since=0`.
    """
    from_nought = get(address, "/api/view?since=0")

    for target in ("/api/view?since=²", "/api/view?since=" + "1" * 4301):
        status, body = asked(address, target)

        assert status == 200, f"{target!r} stopped the handler"
        assert json.loads(body) == from_nought


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

    # The account leads; the step-by-step record is behind a fold.
    assert "Every step" in home
    assert 'id="log-block"' in home
    assert "<details" in home[: home.index("Every step")]

    # A seed nobody has to invent, and one they can keep.
    assert 'id="roll-seed"' in home
    assert 'id="copy-seed"' in home

    # A card shows what it says.
    assert "data-text=" in home


def test_the_step_log_names_the_player_an_event_is_about(address: str) -> None:
    """
    A step is filed under whoever submitted it, which is often not who it is
    about.

    A priority window closes when everybody has passed, so somebody else's pass
    is the command that lets an attack resolve — and at a table of two that is
    always the other player. Every roll of Bo's attack therefore appears under
    Ann, and the log read as though the attacker had changed hands. The
    attacker was in the event the whole time, in ``controller``, and the line
    was not showing it.
    """
    with urllib.request.urlopen(f"{address}/", timeout=10) as answer:
        home = answer.read().decode("utf-8")

    assert "event.controller" in home, (
        "the step log ignores the one field that says who an event is about"
    )
    assert 'class="about"' in home

    # Left off where the event already names that player, or `damage_dealt`
    # prints the player it hurt twice and buries the case this exists for.
    assert "event.targets || []).includes(name)" in home


def test_the_step_log_reads_the_journal_and_does_not_keep_its_own(
    address: str,
) -> None:
    """
    One record, two readings.

    The account and the step log have to be two readings of the same journal.
    If the page assembled the technical log itself, a game where the two
    disagreed would leave nobody able to say which of them was right — so the
    page is only allowed to ask for journal entries it has not drawn.
    """
    with urllib.request.urlopen(f"{address}/", timeout=10) as answer:
        home = answer.read().decode("utf-8")

    assert "/api/journal?since=" in home, "the log is not fed from the journal"

    # Folding and scrolling, both asked of it because games get long.
    assert 'id="log-fold"' in home
    assert "overflow-y: auto" in home


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
