"""
The path a person walks with nothing but the program.

The test is not "the endpoints answer". It is the journey: somebody opens
FSME, makes a set, makes a card, is told what is wrong with it, fixes it,
watches it played, saves it, closes the program and finds it still there.

Every step goes over HTTP exactly as the page does it, and the card that comes
out the far end is loaded by the ordinary content pipeline — because a card
made here has to be a card, not a special kind of card.
"""

from __future__ import annotations

import json
import threading
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


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    A workspace of this test's own, so nothing touches a real one.
    """
    where = tmp_path / "FSME"
    monkeypatch.setenv("FSME_HOME", str(where))

    return where


@pytest.fixture
def address(
    everything: ContentLibrary, tmp_path: Path, home: Path
) -> Iterator[str]:
    bench = Workbench(everything, CONTENT_ROOT, tmp_path / "work")
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


def post(address: str, path: str, body: Any) -> Any:
    request = urllib.request.Request(
        f"{address}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            return json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return json.loads(refused.read())


def page(address: str, path: str) -> str:
    with urllib.request.urlopen(f"{address}{path}", timeout=30) as answer:
        return answer.read().decode("utf-8")


A_PENNY = {
    "name": "Lucky Penny",
    "kind": "loot",
    "text": "Gain 3¢.",
    "ability": {
        "trigger": "on_play",
        "effects": [{"id": "gain_coins", "fields": {"amount": 3}}],
    },
}


# ----------------------------------------------------------------------
# The first screen
# ----------------------------------------------------------------------


def test_the_first_screen_offers_tasks_not_engine_functions(address: str) -> None:
    front = page(address, "/")

    for task in ("Make a card", "My cards", "Watch a game"):
        assert task in front, task

    assert "Run a study" not in front, "a study is not a thing somebody came to do"


def test_the_old_page_is_still_there(address: str) -> None:
    """
    Nothing was taken away — the four tools moved one click further on.
    """
    advanced = page(address, "/advanced")

    for tool in ("Play a game", "Run a study", "Test a card", "Open a report"):
        assert tool in advanced, tool


# ----------------------------------------------------------------------
# Everything the engine can do, without a second list
# ----------------------------------------------------------------------


def test_the_page_is_told_what_the_engine_can_do(address: str) -> None:
    can = get(address, "/api/capabilities")

    assert len(can["effects"]) > 50
    assert len(can["conditions"]) > 30
    assert len(can["targets"]) > 40
    assert len(can["triggers"]) > 60
    assert can["kinds"]


def test_everything_offered_has_words_on_it(address: str) -> None:
    """
    A dropdown of `target_player_or_monster` is not a dropdown anybody can
    use. Every name the page offers carries a sentence, and every sentence
    comes from the engine.
    """
    can = get(address, "/api/capabilities")

    for group in ("effects", "conditions", "targets", "triggers"):
        silent = [one["id"] for one in can[group] if not one.get("about")]

        assert silent == [], f"{group}: {silent}"


def test_the_words_are_the_engines_own(address: str) -> None:
    from fsme.effects import builtin_registry
    from fsme.runtime.target_resolver import TargetResolver

    can = get(address, "/api/capabilities")
    effect = next(one for one in can["effects"] if one["id"] == "gain_coins")
    target = next(one for one in can["targets"] if one["id"] == "target_player")

    assert effect["about"] == builtin_registry().spec("gain_coins").description
    assert target["about"] == TargetResolver().shapes()["target_player"].describes


def test_a_field_knows_what_to_ask_for(address: str) -> None:
    can = get(address, "/api/capabilities")
    effect = next(one for one in can["effects"] if one["id"] == "gain_coins")
    (amount,) = effect["fields"]

    assert amount["about"] == "how many cents"
    assert amount["kind"] == "a whole number"
    assert amount["least"] == 0


# ----------------------------------------------------------------------
# The journey
# ----------------------------------------------------------------------


def test_a_person_can_make_a_card_from_nothing(address: str, home: Path) -> None:
    assert get(address, "/api/sets")["sets"] == [], "nothing to begin with"

    made = post(address, "/api/sets/new", {"name": "My First Set"})

    assert made["id"] == "my_first_set"

    saved = post(address, "/api/cards/save", dict(A_PENNY, set="my_first_set"))

    assert saved["saved"], saved.get("problems")
    assert saved["card"]["id"] == "my_first_set-loot-lucky_penny"

    mine = get(address, "/api/sets")["sets"]

    assert [one["name"] for one in mine] == ["My First Set"]
    assert mine[0]["cards"] == ["Lucky Penny"]


def test_a_card_that_is_wrong_is_not_saved(address: str) -> None:
    post(address, "/api/sets/new", {"name": "Mine"})

    said = post(
        address,
        "/api/cards/save",
        {
            "set": "mine",
            "name": "Odd One",
            "kind": "loot",
            "ability": {
                "trigger": "on_play",
                "effects": [{"id": "gain_coins", "fields": {"amount": "lots"}}],
            },
        },
    )

    assert not said["saved"]
    assert said["problems"]
    assert get(address, "/api/sets")["sets"][0]["cards"] == [], "and nothing was kept"


def test_a_card_is_checked_while_it_is_being_written(address: str) -> None:
    """
    The page asks after every keystroke, so a mistake is seen where it is made
    rather than when it is saved.
    """
    post(address, "/api/sets/new", {"name": "Mine"})

    good = post(address, "/api/cards/check", dict(A_PENNY, set="mine"))
    bad = post(
        address,
        "/api/cards/check",
        {
            "set": "mine",
            "name": "Odd",
            "kind": "loot",
            "ability": {
                "trigger": "on_play",
                "effects": [{"id": "gain_coins", "fields": {"amount": "lots"}}],
            },
        },
    )

    assert good["problems"] == []
    assert bad["problems"]


def test_a_person_can_watch_their_card_being_played(address: str) -> None:
    post(address, "/api/sets/new", {"name": "Mine"})

    watched = post(address, "/api/cards/try", dict(A_PENNY, set="mine"))

    assert watched["problems"] == []
    assert any("gained 3¢" in moment["what"] for moment in watched["moments"]), (
        watched["moments"]
    )


def test_the_harder_card_works_too(address: str) -> None:
    """
    A die roll and a branch — the commonest shape in real Four Souls cards,
    and the second thing anybody tries.
    """
    post(address, "/api/sets/new", {"name": "Mine"})

    gambler = {
        "set": "mine",
        "name": "Gamblers Coin",
        "kind": "loot",
        "text": "Roll: 1-3 lose 1¢. 4-6 gain 4¢.",
        "ability": {
            "trigger": "on_play",
            "effects": [
                {"id": "roll_dice", "fields": {"sides": 6}},
                {
                    "branch": {
                        "condition": {"id": "dice_greater", "fields": {"value": 3}},
                        "then": [{"id": "gain_coins", "fields": {"amount": 4}}],
                        "else": [{"id": "lose_coins", "fields": {"amount": 1}}],
                    }
                },
            ],
        },
    }

    saved = post(address, "/api/cards/save", gambler)

    assert saved["saved"], saved.get("problems")

    ability = saved["card"]["abilities"][0]

    assert ability["effects"][0] == {"effect": "roll_dice", "sides": 6}
    assert ability["effects"][1]["if"] == [{"dice_greater": {"value": 3}}]
    assert ability["effects"][1]["then"] == [{"effect": "gain_coins", "amount": 4}]

    watched = post(address, "/api/cards/try", gambler)

    assert watched["problems"] == []
    assert watched["moments"]


# ----------------------------------------------------------------------
# It is a card, and it stays
# ----------------------------------------------------------------------


def test_what_was_made_is_ordinary_content(address: str, home: Path) -> None:
    """
    The whole point. A card made on the page is loaded by the same pipeline as
    a card somebody typed, with no special case anywhere.
    """
    post(address, "/api/sets/new", {"name": "My First Set"})
    post(address, "/api/cards/save", dict(A_PENNY, set="my_first_set"))

    library = load_content([CONTENT_ROOT, home / "my sets"])

    assert library.registry().get("my_first_set-loot-lucky_penny") is not None
    assert len(library.registry()) == 1046


def test_it_is_still_there_after_the_program_closes(
    address: str, home: Path
) -> None:
    """
    A frozen build keeps the cards we ship inside itself, in a directory the
    operating system wipes. An author's work must not be there, and this is
    the test that says so: nothing but the filesystem is consulted.
    """
    post(address, "/api/sets/new", {"name": "My First Set"})
    post(address, "/api/cards/save", dict(A_PENNY, set="my_first_set"))

    kept = home / "my sets" / "my_first_set" / "cards"
    written = json.loads(
        (kept / "my_first_set-loot-lucky_penny.json").read_text("utf-8")
    )

    assert written["cards"][0]["name"] == "Lucky Penny"
    assert (home / "my sets" / "my_first_set" / "manifest.json").is_file()


def test_two_sets_do_not_collide(address: str) -> None:
    post(address, "/api/sets/new", {"name": "One"})
    post(address, "/api/sets/new", {"name": "Two"})

    post(address, "/api/cards/save", dict(A_PENNY, set="one"))
    post(address, "/api/cards/save", dict(A_PENNY, set="two"))

    assert len(get(address, "/api/sets")["sets"]) == 2


def test_a_set_cannot_be_made_twice(address: str) -> None:
    post(address, "/api/sets/new", {"name": "Mine"})

    said = post(address, "/api/sets/new", {"name": "Mine"})

    assert "already have a set" in said["error"]


def test_a_set_needs_a_usable_name(address: str) -> None:
    assert "needs a name" in post(address, "/api/sets/new", {"name": "  "})["error"]
    assert "no letters" in post(address, "/api/sets/new", {"name": "!!!"})["error"]
