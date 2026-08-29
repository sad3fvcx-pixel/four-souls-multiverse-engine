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
    # Name and identifier: a person reads the one and opening a card needs
    # the other.
    assert [one["name"] for one in mine[0]["cards"]] == ["Lucky Penny"]
    assert mine[0]["cards"][0]["id"] == "my_first_set-loot-lucky_penny"


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
                    "id": "if",
                    "fields": {
                        "if": [{"id": "dice_greater", "fields": {"value": 3}}],
                        "then": [{"id": "gain_coins", "fields": {"amount": 4}}],
                        "else": [{"id": "lose_coins", "fields": {"amount": 1}}],
                    },
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


# ----------------------------------------------------------------------
# Aiming an effect at something
# ----------------------------------------------------------------------


def test_an_effect_can_be_aimed_at_somebody_chosen(address: str) -> None:
    """
    The card that used to come out wrong. "Deal 1 damage" with nothing to aim
    at hits whoever played it — which is the opposite of what a Four Souls
    author writing "deal 1 damage to another player" means, and it validated
    cleanly.
    """
    post(address, "/api/sets/new", {"name": "Mine"})

    saved = post(
        address,
        "/api/cards/save",
        {
            "set": "mine",
            "name": "Shared Burden",
            "kind": "loot",
            "ability": {
                "trigger": "on_play",
                "effects": [
                    {
                        "id": "deal_damage",
                        "fields": {"amount": 1},
                        "aim": "target_player",
                        "aim_fields": {"exclude_controller": True},
                    }
                ],
            },
        },
    )

    assert saved["saved"], saved.get("problems")

    ability = saved["card"]["abilities"][0]

    assert ability["targets"] == [
        {"target_player": {"exclude_controller": True, "as": "chosen_1"}}
    ]
    assert ability["effects"][0]["target"] == "chosen_1"


def test_the_aimed_card_hits_somebody_else(address: str) -> None:
    post(address, "/api/sets/new", {"name": "Mine"})

    watched = post(
        address,
        "/api/cards/try",
        {
            "set": "mine",
            "name": "Shared Burden",
            "kind": "loot",
            "ability": {
                "trigger": "on_play",
                "effects": [
                    {
                        "id": "deal_damage",
                        "fields": {"amount": 1},
                        "aim": "target_player",
                        "aim_fields": {"exclude_controller": True},
                    }
                ],
            },
        },
    )

    hurt = [m["what"] for m in watched["moments"] if "health" in m["what"]]

    assert hurt, watched["moments"]
    assert not any(one.startswith("You lost") for one in hurt), hurt


def test_aiming_twice_at_the_same_thing_chooses_once(address: str) -> None:
    """
    "Deal 1 damage to a player and steal a cent from them" is one player, not
    two. Two effects aimed the same way share the choice.
    """
    post(address, "/api/sets/new", {"name": "Mine"})

    aim = {"aim": "target_player", "aim_fields": {"exclude_controller": True}}
    saved = post(
        address,
        "/api/cards/save",
        {
            "set": "mine",
            "name": "Mugging",
            "kind": "loot",
            "ability": {
                "trigger": "on_play",
                "effects": [
                    dict(id="deal_damage", fields={"amount": 1}, **aim),
                    dict(id="lose_coins", fields={"amount": 1}, **aim),
                ],
            },
        },
    )

    ability = saved["card"]["abilities"][0]

    assert len(ability["targets"]) == 1, "one player, chosen once"
    assert {effect["target"] for effect in ability["effects"]} == {"chosen_1"}


def test_the_page_is_told_what_may_be_aimed_at(address: str) -> None:
    can = get(address, "/api/capabilities")

    # Every one of them. "Destroy what you just damaged" points an effect at
    # `previous_target`, and the engine resolves it like any other.
    assert all(one["aimable"] for one in can["targets"])
    assert len(can["targets"]) > 35

    # The ones that only mean something after the ability has chosen already
    # are offered under their own heading rather than among the rest.
    assert {one["id"] for one in can["targets"] if one["after"]} == {
        "group",
        "most_common",
        "none",
        "previous_result",
        "previous_target",
    }


def test_trying_a_card_the_engine_refuses_answers_rather_than_dies(
    address: str, home: Path
) -> None:
    """
    A card can be well formed and still be one the engine stops on — an
    attack owed zero times is refused by the handler and by nothing before it.

    "Try it in a game" has to say so. Letting the engine's error out of the
    request handler killed the connection, and the page, whose fetch simply
    failed, showed nothing: pressing the button did visibly nothing at all.
    """
    post(address, "/api/sets/new", {"name": "Refused"})

    said = post(
        address,
        "/api/cards/try",
        {
            "set": "refused",
            "name": "Nothing Doing",
            "kind": "loot",
            "ability": {
                "trigger": "on_play",
                "effects": [{"id": "require_attack", "fields": {"times": 0}}],
            },
        },
    )

    assert "error" not in said, said
    assert said["moments"] == []
    assert said["problems"]
    assert "would not play" in said["problems"][0]
    assert "at least one" in said["problems"][0]

    # And the server is still answering, which is the half that used to be
    # missing: the handler thread died with the request.
    assert get(address, "/api/sets")["sets"]


# ----------------------------------------------------------------------
# Being told what is wrong, in one's own words
# ----------------------------------------------------------------------


def test_a_mistake_names_the_box_it_is_in(address: str) -> None:
    """
    Not `abilities[0].effects[0].amount`, and not `gain_coins` either — the
    author picked "Add coins to a player" from a list and typed into a box
    labelled "how many cents".
    """
    post(address, "/api/sets/new", {"name": "Mine"})

    said = post(
        address,
        "/api/cards/check",
        {
            "set": "mine",
            "name": "Odd",
            "kind": "loot",
            "ability": {
                "trigger": "on_play",
                "effects": [{"id": "gain_coins", "fields": {"amount": "three"}}],
            },
        },
    )

    (message,) = said["problems"]

    assert message.startswith("How many cents needs")
    assert "you wrote" in message
    assert "abilities[" not in message
    assert "gain_coins" not in message


def test_a_card_that_does_nothing_is_not_called_ready(address: str) -> None:
    post(address, "/api/sets/new", {"name": "Mine"})

    said = post(
        address,
        "/api/cards/check",
        {
            "set": "mine",
            "name": "Blank",
            "kind": "loot",
            "ability": {"trigger": "on_play", "effects": []},
        },
    )

    (message,) = said["problems"]

    assert "does not do anything yet" in message


# ----------------------------------------------------------------------
# Knowing when things happen
# ----------------------------------------------------------------------


def test_the_moments_a_card_reacts_to_are_distinguishable(address: str) -> None:
    """
    Two of them used to read "damage has been dealt" and "damage is dealt",
    which is not a choice anybody can make.
    """
    can = get(address, "/api/capabilities")
    words = [one["about"] for one in can["triggers"]]

    assert len(words) == len(set(words)), "no two moments read the same"


def test_the_moments_offered_first_are_the_ones_cards_use(address: str) -> None:
    can = get(address, "/api/capabilities")
    first = {one["id"] for one in can["triggers"] if one["common"]}

    for wanted in (
        "turn_start",
        "turn_end",
        "player_died",
        "monster_killed",
        "damage_dealt",
        "on_activate",
        "on_play",
    ):
        assert wanted in first, wanted


def test_a_set_needs_a_usable_name(address: str) -> None:
    assert "needs a name" in post(address, "/api/sets/new", {"name": "  "})["error"]
    assert "no letters" in post(address, "/api/sets/new", {"name": "!!!"})["error"]
