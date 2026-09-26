"""
Two ways in, one card.

The constructor asks what a card should *do* and fills in the rest; the expert
editor asks what a card *is* and lets somebody write every part of it. They are
two views of the same thing, and the moment they stop producing the same card
they have become two editors — with two sets of bugs, two things to keep in
step with the engine, and a card that cannot be opened where it was not made.

So the test is equality, and it is written first on purpose. If it cannot be
made to pass, the design is wrong and no amount of interface work fixes it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.lab.desk import Workbench
from fsme.lab.desk.author import build_card, check_card
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.vocabulary import USED_BY

CONTENT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def can() -> dict[str, Any]:
    return catalogue()


@pytest.fixture(scope="module")
def everything() -> Any:
    return load_content(CONTENT)


@pytest.fixture
def bench(everything: Any, tmp_path: Path) -> Workbench:
    return Workbench(everything, CONTENT, tmp_path / "work")


# ----------------------------------------------------------------------
# The two ways in, written out
# ----------------------------------------------------------------------


def as_the_expert_editor(kind: str, name: str, step: dict[str, Any]) -> Any:
    """
    What the page sends when somebody filled the whole ability in by hand.
    """
    return build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": name,
                    "type": kind,
                    "abilities": [
                        {
                            "fields": {
                                "trigger": USED_BY[kind],
                                "effects": [step],
                            },
                            "groups": {},
                        }
                    ],
                },
                "groups": {},
            },
        }
    )


def as_the_constructor(kind: str, name: str, step: dict[str, Any]) -> Any:
    """
    What the page sends when somebody chose an action and answered its
    questions.

    The difference is only what the *person* was asked. The trigger is not
    invented here: it is the engine's own answer for this kind of card, read
    off the same metadata the page reads. Everything after that is the same
    node, in the same place, going through the same builder.
    """
    trigger = next(
        one["used_by"] for one in catalogue()["kinds"] if one["id"] == kind
    )

    return build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": name,
                    "type": kind,
                    "abilities": [
                        {"fields": {"trigger": trigger, "effects": [step]}}
                    ],
                },
                "groups": {},
            },
        }
    )


COINS = {
    "id": "gain_coins",
    "fields": {"amount": 3},
    "aim": "controller",
    "aim_fields": {},
}
DAMAGE = {
    "id": "deal_damage",
    "fields": {"amount": 1},
    "aim": "target_player",
    "aim_fields": {},
}


# ----------------------------------------------------------------------
# 1. The invariant
# ----------------------------------------------------------------------


def test_the_two_ways_in_make_the_same_card() -> None:
    """
    Byte for byte, not merely equivalent.
    """
    for kind, step in (("loot", COINS), ("loot", DAMAGE), ("treasure", COINS)):
        expert = as_the_expert_editor(kind, "Same", step)
        built = as_the_constructor(kind, "Same", step)

        assert json.dumps(expert, sort_keys=True) == json.dumps(
            built, sort_keys=True
        ), f"{kind} + {step['id']} came out differently"


def test_every_action_makes_the_same_card_either_way(can: dict[str, Any]) -> None:
    """
    Not one effect, every effect. A constructor that agreed about `gain_coins`
    and quietly disagreed about the other sixty-two would be worse than one
    that disagreed about all of them.
    """
    differ = []

    for effect in can["effects"]:
        step: dict[str, Any] = {"id": effect["id"], "fields": {}}

        if effect["needs_target"]:
            step |= {
                "aim": "target_treasure" if effect["hits"] == "cards"
                else "target_player",
                "aim_fields": {},
            }

        expert = as_the_expert_editor("loot", "X", step)
        built = as_the_constructor("loot", "X", step)

        if json.dumps(expert, sort_keys=True) != json.dumps(built, sort_keys=True):
            differ.append(effect["id"])

    assert differ == [], differ


def test_a_constructed_card_goes_through_the_same_checker() -> None:
    """
    One validator. The constructor does not get to decide a card is fine.
    """
    built = as_the_constructor("loot", "Penny", COINS)

    assert check_card(built) == []

    # And it is refused for the same reasons anything else is.
    wrong = as_the_constructor(
        "loot", "Wrong", {"id": "gain_coins", "fields": {"amount": "three"}}
    )

    assert check_card(wrong)


def test_a_constructed_card_plays_in_a_real_game(bench: Workbench) -> None:
    """
    One runtime, reached the one way.
    """
    built = as_the_constructor("loot", "Penny", COINS)
    moments = [one["what"] for one in bench.show_card(built)]

    assert any("gained" in one for one in moments), moments


# ----------------------------------------------------------------------
# 2. The fact the constructor needs, and where it comes from
# ----------------------------------------------------------------------


def test_how_a_card_is_used_is_the_engines_answer_and_not_a_table() -> None:
    """
    The one thing the constructor knows that the editor does not ask: which
    moment makes this kind of card do its thing. It is read from beside the
    rules that decide it, so changing the rule changes this.
    """
    from fsme.rules.activation import ACTIVATED_BY
    from fsme.rules.loot import PLAYED_BY

    assert USED_BY["loot"] == str(PLAYED_BY)
    assert USED_BY["treasure"] == str(ACTIVATED_BY)


def test_a_loot_card_written_against_that_moment_actually_does_something(
    bench: Workbench,
) -> None:
    """
    The claim, checked against behaviour rather than against itself.

    A loot card on any other trigger is played and nothing happens, which is
    exactly the card a constructor would produce if this fact were wrong.
    """
    right = as_the_constructor("loot", "Right", COINS)

    assert any("gained" in one["what"] for one in bench.show_card(right))

    wrong = build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Wrong",
                    "type": "loot",
                    "abilities": [
                        {"fields": {"trigger": "turn_start", "effects": [COINS]}}
                    ],
                },
                "groups": {},
            },
        }
    )

    assert not any("gained" in one["what"] for one in bench.show_card(wrong))


def test_nothing_is_claimed_for_the_kinds_the_engine_does_not_settle(
    can: dict[str, Any],
) -> None:
    """
    A monster reacts to several moments and no one of them is *the* moment.
    Filling one in would put a trigger on a card that never fires.
    """
    said = {one["id"]: one["used_by"] for one in can["kinds"]}

    assert said["loot"]
    assert said["treasure"]
    assert said["monster"] == ""
    assert said["room"] == ""
    assert said["character"] == ""
