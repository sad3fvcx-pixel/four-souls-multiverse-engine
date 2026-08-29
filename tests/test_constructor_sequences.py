"""
A card that does two things, and then a third.

The engine has always allowed it — an ability holds a *list* of steps, the
builder hoists each step's aim into its own binding, and the runtime runs them
in order. The walk was the only thing that could say one and only one.

These are the tests for saying more than one, written before the screens that
say it. Everything they check is a property of the card that comes out, so they
hold whichever way in built it: the two ways in still make one card, the order
somebody answered in is the order the engine runs, and a card with one action
is exactly the card the previous release made.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_constructor_walk import (  # the walk, written out from the metadata
    CONTENT,
    a_step,
    aims_at,
    asked_about,
    offered,
)

from fsme.api import load_content
from fsme.lab.desk import Workbench
from fsme.lab.desk.author import build_card, check_card
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.vocabulary import USED_BY


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
# The two ways in, with a list of actions rather than one
# ----------------------------------------------------------------------


def as_the_walk(can: dict[str, Any], doing: list[Any], name: str = "Walked") -> Any:
    """
    What a walk sends after somebody answered for each action in turn.

    The trigger is the engine's own answer for this kind of card, read off the
    published metadata; the actions are one list, in the order they were said.
    """
    trigger = next(one["used_by"] for one in can["kinds"] if one["id"] == "loot")

    return build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": name,
                    "type": "loot",
                    "abilities": [
                        {
                            "fields": {
                                "trigger": trigger,
                                "effects": [a_step(can, one) for one in doing],
                            }
                        }
                    ],
                },
                "groups": {},
            },
        }
    )


def as_the_editor(can: dict[str, Any], doing: list[Any], name: str = "Walked") -> Any:
    """
    The same card, with every part of it filled in by hand.
    """
    return build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": name,
                    "type": "loot",
                    "abilities": [
                        {
                            "fields": {
                                "trigger": USED_BY["loot"],
                                "effects": [a_step(can, one) for one in doing],
                            },
                            "groups": {},
                        }
                    ],
                },
                "groups": {},
            },
        }
    )


def heads(card: Any) -> list[str]:
    """
    The effects of a built card, in the order the engine will run them.
    """
    return [str(step["effect"]) for step in card["abilities"][0]["effects"]]


def sample(can: dict[str, Any]) -> list[tuple[Any, Any]]:
    """
    Ordered pairs of actions, chosen so the choice cannot drift.

    Every ordered pair of the actions shown first, which is what somebody
    building a two-step card will most often reach for, plus one pass over the
    whole offer list pairing each action with its neighbour so that nothing is
    only ever tested against the common few. Deterministic on purpose: a
    randomly sampled invariant is an invariant that fails on somebody else's
    machine.
    """
    all_of = offered(can)
    common = [one for one in all_of if one.get("common")]
    pairs = [(a, b) for a in common for b in common]
    pairs += [
        (all_of[i], all_of[(i + 1) % len(all_of)])
        for i in range(0, len(all_of), 2)
    ]

    return pairs


@pytest.fixture(scope="module")
def pairs(can: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Every sampled pair, built both ways, once.

    Building a card is forty milliseconds and the sample is in the hundreds, so
    each way in is walked once here rather than once per test.
    """
    return [
        {
            "says": f"{a['id']} then {b['id']}",
            "ids": [a["id"], b["id"]],
            "walk": as_the_walk(can, [a, b]),
            "editor": as_the_editor(can, [a, b]),
        }
        for a, b in sample(can)
    ]


# ----------------------------------------------------------------------
# 1. The invariant, over sequences
# ----------------------------------------------------------------------


def test_the_two_ways_in_make_the_same_card_with_several_actions(
    pairs: list[dict[str, Any]],
) -> None:
    """
    Byte for byte, over every sampled ordered pair.
    """
    differ = [
        one["says"]
        for one in pairs
        if json.dumps(one["walk"], sort_keys=True)
        != json.dumps(one["editor"], sort_keys=True)
    ]

    assert differ == [], differ[:10]


def test_one_action_still_makes_exactly_the_card_it_used_to(
    can: dict[str, Any],
) -> None:
    """
    The change is additive or it is a regression.

    A list of one is written exactly as the single action was: nothing about
    the card says it was built by a walk that can now say more.
    """
    for one in offered(can):
        listed = as_the_walk(can, [one], "Same")
        alone = build_card(
            {
                "set": "demo",
                "card": {
                    "fields": {
                        "name": "Same",
                        "type": "loot",
                        "abilities": [
                            {
                                "fields": {
                                    "trigger": USED_BY["loot"],
                                    "effects": [a_step(can, one)],
                                }
                            }
                        ],
                    },
                    "groups": {},
                },
            }
        )

        assert json.dumps(listed, sort_keys=True) == json.dumps(
            alone, sort_keys=True
        ), one["id"]


# ----------------------------------------------------------------------
# 2. Order
# ----------------------------------------------------------------------


def test_the_order_answered_is_the_order_written(
    pairs: list[dict[str, Any]],
) -> None:
    """
    A card that damages and then pays is not a card that pays and then damages.
    """
    wrong = [one["says"] for one in pairs if heads(one["walk"]) != one["ids"]]

    assert wrong == [], wrong[:10]


def test_swapping_two_actions_makes_a_different_card(can: dict[str, Any]) -> None:
    """
    And the difference survives being built — an order the builder flattened
    away would be an order the runtime could not honour.
    """
    all_of = offered(can)
    first = next(one for one in all_of if one["id"] == "deal_damage")
    second = next(one for one in all_of if one["id"] == "gain_coins")

    one_way = json.dumps(as_the_walk(can, [first, second]), sort_keys=True)
    other = json.dumps(as_the_walk(can, [second, first]), sort_keys=True)

    assert one_way != other


def test_a_third_action_goes_on_the_end(can: dict[str, Any]) -> None:
    """
    Nothing about the second action is special: the list is a list.
    """
    all_of = offered(can)
    three = [
        next(one for one in all_of if one["id"] == name)
        for name in ("deal_damage", "gain_coins", "draw_loot")
    ]

    assert heads(as_the_walk(can, three)) == [
        "deal_damage",
        "gain_coins",
        "draw_loot",
    ]


# ----------------------------------------------------------------------
# 3. Each action keeps its own aim
# ----------------------------------------------------------------------


def test_every_action_is_aimed_on_its_own(can: dict[str, Any]) -> None:
    """
    Two actions that both pick something out bind two names, and each step
    points at its own. Sharing one binding would silently make the second
    action happen to whatever the first one chose.
    """
    all_of = offered(can)
    aiming = [one for one in all_of if one["needs_target"]][:8]

    for a in aiming:
        for b in aiming:
            card = as_the_walk(can, [a, b])
            ability = card["abilities"][0]
            bound = [
                next(iter(spec.values()))["as"]
                for spec in ability.get("targets", ())
            ]
            pointed = [step.get("target") for step in ability["effects"]]

            assert len(set(bound)) == len(bound), f"{a['id']}/{b['id']}: {bound}"
            assert pointed[0] != pointed[1] or aims_at(can, a) == aims_at(can, b)
            assert all(one in bound for one in pointed if one)


# ----------------------------------------------------------------------
# 4. A sequence is a card the engine takes
# ----------------------------------------------------------------------


def test_every_sampled_sequence_passes_the_checker(
    pairs: list[dict[str, Any]],
) -> None:
    """
    One validator, and no exceptions list for sequences.
    """
    refused = {
        one["says"]: check_card(one["walk"])[0]
        for one in pairs
        if check_card(one["walk"])
    }

    assert refused == {}, dict(list(refused.items())[:6])


def test_a_sequence_loads_and_plays(bench: Workbench, can: dict[str, Any]) -> None:
    """
    Through the runtime, in a real game.

    The card the brief asks for: deal two damage to a player, then gain three
    cents.
    """
    all_of = offered(can)
    damage = next(one for one in all_of if one["id"] == "deal_damage")
    coins = next(one for one in all_of if one["id"] == "gain_coins")
    card = as_the_walk(can, [damage, coins], "One Two")

    assert check_card(card) == []
    assert heads(card) == ["deal_damage", "gain_coins"]
    assert bench.show_card(card), "the card reached no moment at all"


def test_the_sequences_that_do_not_play_are_the_known_ones(
    bench: Workbench, can: dict[str, Any]
) -> None:
    """
    A sequence plays unless one of its actions was already the kind that does
    not — the three the coarse target vocabulary cannot describe. Adding a
    second action introduces no new refusal of its own.
    """
    from test_constructor_walk import COARSER_THAN_THEY_ARE

    all_of = offered(can)
    fine = [one for one in all_of if one["id"] not in COARSER_THAN_THEY_ARE]
    broke = []

    for i in range(0, len(fine), 3):
        a, b = fine[i], fine[(i + 1) % len(fine)]

        try:
            bench.show_card(as_the_walk(can, [a, b], "Pair"))
        except Exception:  # noqa: BLE001 - the reason belongs to the effect
            broke.append(f"{a['id']} then {b['id']}")

    assert broke == [], broke


# ----------------------------------------------------------------------
# 5. What the page must be able to say
# ----------------------------------------------------------------------


def test_an_ability_says_it_holds_more_than_one_action(can: dict[str, Any]) -> None:
    """
    The permission to add a second action is the metadata's, not the page's.

    `effects` is declared a list, and a list is how this language says more
    than one is allowed. A walk that read that would extend to a second
    ability without new code, because `abilities` is a list for the same
    reason — so this checks both.
    """
    ability = next(one for one in can["abilities"] if one["id"] == "ability")
    holds = [f for f in ability["fields"] if f["a_list_of"] == "step"]

    assert holds, "an ability no longer says where the things it does go"

    card = next(one for one in can["cards"] if one["id"] == "card")
    parts = [f for f in card["fields"] if f["a_list_of"] == "ability"]

    assert parts, "a card no longer says where its abilities go"


def test_every_sampled_sequence_is_of_actions_a_walk_offers(
    can: dict[str, Any],
) -> None:
    """
    The sample is drawn from the offer list, so a rule that stops offering
    something stops testing it too, rather than testing a card nobody can make.
    """
    offers = {one["id"] for one in offered(can)}
    stray = [
        one for a, b in sample(can)
        for one in (a["id"], b["id"]) if one not in offers
    ]

    assert stray == [], stray


def test_a_walk_asks_few_enough_questions_for_two_actions(
    can: dict[str, Any],
) -> None:
    """
    Two actions is two sets of questions, and a walk that turns into a form has
    stopped being a walk. Six is the line the plan drew.
    """
    def cost(one: Any) -> int:
        return len(asked_about(one)) + (1 if one["needs_target"] else 0)

    common = [one for one in offered(can) if one.get("common")]
    worst = max(cost(a) + cost(b) for a in common for b in common)

    assert worst <= 6, worst


# ----------------------------------------------------------------------
# 6. The screen between actions
# ----------------------------------------------------------------------

PAGE = CONTENT.parent / "src/fsme/lab/desk/static/author.html"


def test_the_page_has_a_screen_between_actions() -> None:
    """
    Adding an action is choosing one, from the same list, for the same moment.
    """
    script = PAGE.read_text("utf-8").split("<script>")[1]

    assert "function sofar(" in script
    assert "function addAction()" in script
    # The second action goes through the same chooser as the first.
    assert "chooseAction(walk.how)" in script
    # And it is pushed onto the list the ability already holds — there is no
    # second place in the card for a second action.
    assert "doing.push(" in script


def test_the_page_reads_an_action_back_without_naming_one(
    can: dict[str, Any],
) -> None:
    """
    The list between actions is words, built from the metadata: the sentence
    the effect carries and the questions that were answered. An effect named
    here would be an effect the next one does not get read back.
    """
    script = PAGE.read_text("utf-8").split("<script>")[1]

    assert "function saidAs(" in script

    named = [one["id"] for one in can["effects"] if f'"{one["id"]}"' in script]

    assert named == [], named


def test_the_list_between_actions_is_not_the_editor() -> None:
    """
    It reads the card back rather than offering it for editing.

    `bodyHtml` is what draws a list of nodes as controls, and drawing one here
    would make this screen a second, smaller expert editor — the duplication
    the whole design exists to avoid.
    """
    script = PAGE.read_text("utf-8").split("<script>")[1]
    between = script.split("function sofar(")[1].split("\nfunction ")[0]

    assert "bodyHtml" not in between
    assert "oneByOne" not in between
    assert "valueHtml" not in between
