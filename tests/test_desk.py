"""
The front door.

The desk is a launcher and nothing more: it starts the same functions the
command line starts and shows their output unchanged. So the tests are about it
staying that — that the game it was built on still works exactly as it did,
that work happens in the background instead of in a request, that a name typed
into a browser cannot reach outside the work directory, and that a job which
fails says so instead of disappearing.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from fsme.api import Session, load_content
from fsme.content import ContentLibrary
from fsme.lab.desk import Workbench, desk

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

PATIENCE = 120.0


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture
def bench(everything: ContentLibrary, tmp_path: Path) -> Workbench:
    return Workbench(everything, CONTENT_ROOT, tmp_path / "work")


@pytest.fixture
def address(everything: ContentLibrary, bench: Workbench) -> Iterator[str]:
    server = desk(
        Session(everything, players=2, seed=7), bench, host="127.0.0.1", port=0
    )

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
    with urllib.request.urlopen(f"{address}{path}", timeout=30) as answer:
        return json.loads(answer.read())


def page(address: str, path: str) -> str:
    with urllib.request.urlopen(f"{address}{path}", timeout=30) as answer:
        return answer.read().decode("utf-8")


def post(address: str, path: str, body: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        f"{address}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=30) as answer:
        return json.loads(answer.read())


def finished(address: str, number: int) -> Any:
    """
    Wait for one job, the way the page does.
    """
    until = time.monotonic() + PATIENCE

    while time.monotonic() < until:
        job = get(address, f"/api/jobs/{number}")

        if job["state"] in ("done", "failed"):
            return job

        time.sleep(0.2)

    raise AssertionError(f"job {number} never finished")


def test_the_front_door_is_the_four_things(address: str) -> None:
    home = page(address, "/")

    for what in ("Play a game", "Run a study", "Test a card", "Open a report"):
        assert what in home, what


def test_the_game_is_still_where_it_was(address: str) -> None:
    # The desk is built on the game server, and breaking the game to add a
    # launcher would be a poor trade.
    assert "<html" in page(address, "/play").lower()

    view = get(address, "/api/view?since=0")

    assert set(view) == {"events", "history_length", "moves", "state"}
    assert view["state"]["players"]


def test_a_command_still_reaches_the_engine(address: str) -> None:
    answer = post(address, "/api/command", {"type": "start_game", "player": 0})

    assert "view" in answer


def test_the_cards_are_offered_for_completion(address: str) -> None:
    cards = get(address, "/api/cards")["cards"]

    assert cards
    assert all(card["id"] and card["name"] for card in cards)


def test_a_game_can_be_played_and_then_reported_on(address: str) -> None:
    started = post(
        address, "/api/run", {"kind": "play", "seed": 3, "players": 2}
    )

    assert started["state"] in ("waiting", "running", "done")

    job = finished(address, started["id"])

    assert job["state"] == "done", job["error"]
    assert "FSME GAME REPORT" in job["text"]
    assert job["saved"]

    # And the game it saved can be read again from the page.
    saved = get(address, "/api/journals")["journals"]

    assert [one["name"] for one in saved] == [job["saved"]]

    again = finished(
        address,
        post(address, "/api/run", {"kind": "report", "name": job["saved"]})["id"],
    )

    assert again["state"] == "done", again["error"]
    assert "FSME GAME REPORT" in again["text"]


def test_a_study_reports_how_far_it_has_got(address: str) -> None:
    started = post(
        address,
        "/api/run",
        {"kind": "study", "games": 4, "players": 2, "jobs": 2},
    )

    job = finished(address, started["id"])

    assert job["state"] == "done", job["error"]
    assert job["total"] == 4
    assert job["done"] == 4
    assert "FSME study" in job["text"]


def test_the_page_prints_what_the_command_prints(
    address: str, everything: ContentLibrary
) -> None:
    """
    One answer, not two.

    A button that produced a slightly different report from the command would
    make the first disagreement between them unanswerable.
    """
    from fsme.lab.analysis import review, reviewed
    from fsme.lab.simulation import play_one

    job = finished(
        address,
        post(address, "/api/run", {"kind": "play", "seed": 3, "players": 2})["id"],
    )

    journal, _ = play_one(everything, 3, 2)

    assert job["text"] == reviewed(review(journal, everything))


def test_a_job_that_fails_says_so(address: str) -> None:
    started = post(
        address,
        "/api/run",
        {"kind": "test-card", "card": "no-such-card", "games": 1},
    )

    job = finished(address, started["id"])

    assert job["state"] == "failed"
    assert job["error"]


def test_a_name_cannot_reach_outside_the_work_directory(
    address: str, bench: Workbench
) -> None:
    job = finished(
        address,
        post(
            address,
            "/api/run",
            {"kind": "report", "name": "../../../etc/passwd"},
        )["id"],
    )

    assert job["state"] == "failed"
    assert "/etc/passwd" not in job["text"]


def test_a_run_it_does_not_know_is_refused(address: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as raised:
        post(address, "/api/run", {"kind": "nonsense"})

    assert raised.value.code == 400


def test_a_run_asking_for_too_much_is_brought_back_in_range() -> None:
    """
    A typed digit too many is an easy mistake to make and a hard one to notice.

    Checked on the reader rather than by starting a run, because a test that
    proved the limit by launching five thousand games would be demonstrating
    the problem rather than the fix.
    """
    from fsme.lab.desk.server import MOST_GAMES, _within

    assert _within(10_000_000, 100, low=1, high=MOST_GAMES) == MOST_GAMES
    assert _within(99, 2, low=1, high=4) == 4
    assert _within(-5, 2, low=1, high=4) == 1

    assert _within(None, 2, low=1, high=4) == 2
    assert _within("nonsense", 7, low=1, high=99) == 7


# ----------------------------------------------------------------------
# What the first user found
# ----------------------------------------------------------------------


def test_a_card_can_be_told_apart_from_the_others_that_share_its_name(
    address: str, everything: ContentLibrary
) -> None:
    """
    The path a name takes: card data → the workbench → the page.

    The picker used to be a datalist whose option *value* was the identifier,
    and a datalist shows the value. So the user testing a card saw
    `loot_deck-cards_miscellaneous-four_souls-gold_key` where they expected
    "Gold Key". The name was never broken; it was never shown.

    A name alone would not have been enough either: twelve cards are called
    "Pills!". So the set travels with it, and the names here are asserted
    against the content itself rather than against a copy.
    """
    served = get(address, "/api/cards")["cards"]

    truth = {
        definition.id: definition.name
        for definition in everything.definitions()
    }

    assert len(served) == len(truth)

    for card in served:
        assert card["name"] == truth[card["id"]], card["id"]

        assert card["set"], f"{card['id']} has no set to tell it apart"
        assert isinstance(card["implemented"], bool)

    # And the ambiguity that made the set necessary is real.
    names = [card["name"] for card in served]

    assert names.count("Pills!") > 1


def test_the_page_shows_the_name_and_submits_the_identifier(
    address: str,
) -> None:
    home = page(address, "/")

    # A select, not a datalist: a datalist displays what it submits.
    assert "<datalist" not in home
    assert 'option.textContent = one.implemented' in home
    assert "option.value = one.id" in home


def test_every_seat_can_be_played_by_the_bot(address: str) -> None:
    """
    The detailed log only exists for a game somebody plays through.

    Before this the page could put one seat under the bot; the rest played at
    random, so the readable log was three quarters noise.
    """
    started = post(
        address,
        "/api/run",
        {"kind": "play", "seed": 7, "players": 3, "bot_seats": [0, 1, 2]},
    )

    job = finished(address, started["id"])

    assert job["state"] == "done", job["error"]
    assert "Seats 0, 1, 2 were played by that bot" in job["text"]

    home = page(address, "/")

    assert "every seat by the bot" in home


def test_a_report_can_be_saved_and_opened_again(address: str) -> None:
    """
    The file carries the game, not the prose.

    Saving only the text would make a souvenir: every analyser in the project
    reads games, so a report nobody can re-ask a question of is a dead end.
    """
    job = finished(
        address,
        post(address, "/api/run", {"kind": "play", "seed": 5, "players": 2})["id"],
    )

    with urllib.request.urlopen(f"{address}/api/report/{job['id']}") as answer:
        assert "attachment" in answer.headers.get("Content-Disposition", "")

        bundle = json.loads(answer.read())

    assert bundle["fsme_report"] == 1
    assert bundle["journal"]["entries"], "the game did not travel with the report"
    assert bundle["text"] == job["text"]

    # Loading re-runs the analysers rather than replaying the stored text, so a
    # report opened in a later FSME is that FSME's report.
    again = finished(address, post(address, "/api/load", bundle)["id"])

    assert again["state"] == "done", again["error"]
    assert again["text"] == job["text"]


def test_a_file_that_is_not_a_report_is_refused_by_name(address: str) -> None:
    for body, expected in (
        ({"hello": 1}, "not an FSME report"),
        ({"fsme_report": 99, "journal": {}}, "saved by a newer version"),
        ({"fsme_report": 1}, "no game in it"),
    ):
        with pytest.raises(urllib.error.HTTPError) as raised:
            post(address, "/api/load", body)

        assert raised.value.code == 400
        assert expected in json.loads(raised.value.read())["error"]


def test_a_study_has_no_one_game_to_save(address: str) -> None:
    # A study is about four hundred games; there is no single game to send with
    # it, and the page disables the button rather than writing a broken file.
    job = finished(
        address,
        post(
            address,
            "/api/run",
            {"kind": "study", "games": 4, "players": 2, "jobs": 2},
        )["id"],
    )

    assert not job["saved"]

    with pytest.raises(urllib.error.HTTPError) as raised:
        get(address, f"/api/report/{job['id']}")

    assert raised.value.code == 404


def test_the_bots_can_play_the_game_being_watched(address: str) -> None:
    """
    The detailed log lives in the game somebody watches, not in a report.

    Before this the only way to fill it was to play every move by hand, so
    "show me what FSME does" meant "play a game of Four Souls first".
    """
    request = urllib.request.Request(f"{address}/api/autoplay", method="HEAD")

    with urllib.request.urlopen(request, timeout=10) as answer:
        assert answer.status == 200, "the desk should offer to play"

    post(address, "/api/command", {"type": "start_game", "player": 0})

    moved = 0
    over = False

    for _ in range(60):
        answer = post(address, "/api/autoplay", {"moves": 16})

        moved += answer["moved"]
        over = answer["over"]

        if not answer["moved"] or over:
            break

    assert moved > 20, "the bots barely moved"

    told = [one["said"] for one in answer["view"]["events"] if one["said"]]

    assert told, "a game was played and nothing was said about it"


def test_a_card_says_what_it_does_before_it_is_measured(address: str) -> None:
    cards = get(address, "/api/cards")["cards"]

    named = {card["id"]: card for card in cards}

    bone = named["starting_items-base_game-the_bone"]

    assert bone["name"] == "The Bone"
    assert bone["text"], "the printed text never reached the page"
    assert "counter" in bone["text"].lower()

    home = page(address, "/")

    assert 'id="card-text"' in home
