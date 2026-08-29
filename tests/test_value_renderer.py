"""
The values flowing through the language, as the renderer now sees them.

Three things the metadata said and nothing could draw: that a value may be
given more than one way, that it may be the name of something an earlier step
made, and that its choices wait on another answer in the same node.

The page is JavaScript, so what is tested is the metadata it reads and the card
it produces, plus the shape of the renderer itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fsme.cards import validate_card
from fsme.lab.desk.author import build_card, check_card
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.vocabulary import engine_vocabulary

PAGE = (
    Path(__file__).resolve().parents[1]
    / "src/fsme/lab/desk/static/author.html"
)


@pytest.fixture(scope="module")
def can() -> dict[str, Any]:
    return catalogue()


@pytest.fixture(scope="module")
def page() -> str:
    return PAGE.read_text("utf-8")


@pytest.fixture(scope="module")
def vocabulary():
    return engine_vocabulary()


def complain(vocabulary, card: dict[str, Any]) -> list[str]:
    said = validate_card(
        card,
        known_effects=vocabulary.effects,
        known_triggers=vocabulary.triggers,
        known_conditions=vocabulary.conditions,
        known_targets=vocabulary.targets,
        shapes=vocabulary.shapes,
        condition_shapes=vocabulary.condition_shapes,
        target_shapes=vocabulary.target_shapes,
        node_shapes=vocabulary.node_shapes,
    )

    return [one for one in said if "missing required field" not in one]


def a_card(effects: list[dict[str, Any]]) -> dict[str, Any]:
    return build_card(
        {
            "set": "demo",
            "name": "Under Test",
            "kind": "loot",
            "ability": {"trigger": "on_play", "effects": effects},
        }
    )


def raw(**ability: Any) -> dict[str, Any]:
    return {
        "id": "x",
        "name": "X",
        "type": "treasure",
        "expansion": "x",
        "schema_version": "1",
        "abilities": [{"trigger": "on_play", **ability}],
    }


# ----------------------------------------------------------------------
# 1. A literal is still a literal
# ----------------------------------------------------------------------


def test_a_literal_value_writes_exactly_what_it_always_did() -> None:
    card = a_card(
        [
            {"id": "roll_dice", "fields": {"sides": 6}},
            {"id": "deal_damage", "fields": {"amount": 2}},
        ]
    )

    assert card["abilities"][0]["effects"] == [
        {"effect": "roll_dice", "sides": 6},
        {"effect": "deal_damage", "amount": 2},
    ]
    assert check_card(card) == []


def test_every_shipped_card_still_loads() -> None:
    from fsme.api import load_content

    root = Path(__file__).resolve().parents[1] / "content"

    assert load_content(root) is not None


# ----------------------------------------------------------------------
# 2. A value may be given more than one way
# ----------------------------------------------------------------------


def test_a_parameter_offers_its_ways(can: dict[str, Any]) -> None:
    amount = next(
        f
        for one in can["effects"]
        if one["id"] == "deal_damage"
        for f in one["fields"]
        if f["id"] == "amount"
    )

    assert amount["kind"] == "a whole number"
    assert [way["shaped_like"] for way in amount["also"]] == ["worked_out"]


def test_the_page_asks_which_way_and_draws_that_way(page: str) -> None:
    assert "function waysHtml(f, values, siblings, path, owner)" in page
    assert "function writtenThisWay(way, value)" in page
    assert "if (f.also.length) return waysHtml" in page
    # The way is read off the value's own shape, so nothing is remembered
    # beside the card.
    assert "typeof value === \"object\"" in page


def test_a_value_worked_out_survives_the_round_trip() -> None:
    card = a_card(
        [
            {"id": "roll_dice", "fields": {}},
            {"id": "deal_damage", "fields": {"amount": {"from": "dice"}}},
        ]
    )

    assert card["abilities"][0]["effects"][1] == {
        "effect": "deal_damage",
        "amount": {"from": "dice"},
    }
    assert check_card(card) == []


def test_a_counted_value_survives_too() -> None:
    card = a_card(
        [{"id": "draw_loot", "fields": {"count": {"count": "loot", "of": "rival"}}}]
    )
    node = card["abilities"][0]["effects"][0]

    assert node["count"] == {"count": "loot", "of": "rival"}


def test_a_way_of_working_it_out_that_nobody_reads_is_refused(vocabulary) -> None:
    said = complain(
        vocabulary,
        raw(effects=[{"effect": "deal_damage", "amount": {"whence": "dice"}}]),
    )

    assert said
    assert "worked_out" in said[0]


def test_counting_something_nothing_counts_is_refused(vocabulary) -> None:
    assert complain(
        vocabulary,
        raw(effects=[{"effect": "draw_loot", "count": {"count": "biscuits"}}]),
    )


def test_two_ways_at_once_is_refused(vocabulary) -> None:
    """
    The executor tries them in the order it lists them and takes the first, so
    a card writing two has written one and a sentence nobody reads.
    """
    said = complain(
        vocabulary,
        raw(
            effects=[
                # The roll is there so that `from` names something real: this
                # is about writing two ways at once, and a card that also
                # reads a value nothing stored would be refused twice for two
                # different reasons.
                {"effect": "roll_dice"},
                {
                    "effect": "deal_damage",
                    "amount": {"from": "dice", "from_event": "amount"},
                },
            ]
        ),
    )

    assert said
    assert "only one of" in said[0]


def test_the_page_offers_one_of_a_group_as_one_question(page: str) -> None:
    assert "function oneOfHtml(group, siblings, values, path, owner)" in page
    assert "function setOneOf(path, group, id, owner)" in page
    assert "if (f.one_of)" in page


def test_the_engine_says_which_parameters_are_one_of_a_group(
    can: dict[str, Any],
) -> None:
    worked = next(
        one for one in can["structures"] if one["id"] == "worked_out"
    )
    grouped = {f["id"] for f in worked["fields"] if f["one_of"]}

    assert grouped == {"from", "from_event", "last_result", "count", "player_of"}

    from fsme.cards.validator import DYNAMIC_HEADS

    assert grouped == set(DYNAMIC_HEADS)


# ----------------------------------------------------------------------
# 3. A name one step makes and another reads
# ----------------------------------------------------------------------


def test_an_effect_that_keeps_its_result_says_what_it_keeps_it_under(
    can: dict[str, Any],
) -> None:
    from fsme.effects import builtin_registry

    registry = builtin_registry()
    published = {one["id"]: one["stores"] for one in can["effects"] if one["stores"]}

    assert published == {"roll_dice": "dice", "reroll": "dice"}

    for name, under in published.items():
        assert registry.spec(name).stores == under


def test_a_field_that_invents_a_name_says_so(can: dict[str, Any]) -> None:
    store = next(
        f
        for one in can["structures"]
        if one["id"] == "if"
        for f in one["fields"]
        if f["id"] == "store"
    )

    assert store["defines"] == "values"
    assert store["role"] == "defines"


def test_the_page_offers_the_names_it_can_find_rather_than_a_box(
    page: str,
) -> None:
    assert "function referenceHtml(f, values, path)" in page
    # Which names there are is a question about one part of a card, not about
    # the card: the engine gives every ability a context of its own.
    assert "function definedNames(kind, path)" in page
    # Found by asking each node's own shape what it defines and what it keeps.
    assert "shape.stores" in page
    assert "f.defines === kind" in page
    # And when there is nothing to point at, it says what would make one
    # rather than leaving a dead end. Which effects those are is read off the
    # metadata, so it is the mechanism that is pinned here, not a list.
    assert "Nothing earlier in this card remembers a value yet." in page
    assert "function whatWouldMakeOne(kind)" in page
    assert "can.effects.filter(e => e.stores)" in page


def test_a_reference_is_not_free_text(can: dict[str, Any]) -> None:
    reading = next(
        f
        for one in can["conditions"]
        if one["id"] == "values_equal"
        for f in one["fields"]
        if f["id"] == "of"
    )

    assert reading["picks"] == "values"
    assert reading["written"] == "the name of a value an earlier step stored"


def test_reading_a_name_an_earlier_step_made_makes_a_card() -> None:
    card = a_card(
        [
            {"id": "roll_dice", "fields": {"sides": 6}},
            {
                "id": "if",
                "fields": {
                    "if": [{"id": "values_equal", "fields": {"of": "dice"}}],
                    "then": [{"id": "gain_coins", "fields": {"amount": 1}}],
                },
            },
        ]
    )

    assert check_card(card) == []
    assert card["abilities"][0]["effects"][1]["if"] == [
        {"values_equal": {"of": "dice"}}
    ]


# ----------------------------------------------------------------------
# 4. Choices that wait on another answer
# ----------------------------------------------------------------------


def test_a_dependent_choice_publishes_the_branches_it_knows(
    can: dict[str, Any],
) -> None:
    from fsme.rules.statics import STATIC_SCOPES
    from fsme.state.modifiers import MONSTER_STATS, STATS

    stat = next(
        f for one in can["statics"] for f in one["fields"] if f["id"] == "stat"
    )

    assert stat["domain_from"] == "scope"
    assert set(stat["domains"]) == set(STATIC_SCOPES) - {"self"}
    assert stat["domains"]["controller"] == list(STATS)
    assert stat["domains"]["all_monsters"] == list(MONSTER_STATS)


def test_the_answer_it_cannot_resolve_is_left_out_rather_than_guessed(
    can: dict[str, Any],
) -> None:
    """
    `self` settles it only together with the kind of card the static is on,
    which is not one of the static's own answers. A union would be a list that
    is right half the time.
    """
    stat = next(
        f for one in can["statics"] for f in one["fields"] if f["id"] == "stat"
    )

    assert "self" not in stat["domains"]


def test_the_page_says_why_when_it_cannot_work_the_list_out(page: str) -> None:
    assert "function dependentHtml(f, values, siblings, path)" in page
    assert "cannot work it out from the card alone" in page


def test_a_stat_outside_what_its_scope_allows_is_refused(vocabulary) -> None:
    card = {
        "id": "x",
        "name": "X",
        "type": "treasure",
        "expansion": "x",
        "schema_version": "1",
        "statics": [{"stat": "difficulty", "amount": 1, "scope": "controller"}],
        "abilities": [
            {"trigger": "on_play", "effects": [{"effect": "gain_coins", "amount": 1}]}
        ],
    }
    said = complain(vocabulary, card)

    assert said
    assert "'scope' allows here" in said[0]


def test_the_same_stat_is_accepted_where_its_scope_allows_it(vocabulary) -> None:
    card = {
        "id": "x",
        "name": "X",
        "type": "treasure",
        "expansion": "x",
        "schema_version": "1",
        "statics": [{"stat": "difficulty", "amount": 1, "scope": "all_monsters"}],
        "abilities": [
            {"trigger": "on_play", "effects": [{"effect": "gain_coins", "amount": 1}]}
        ],
    }

    assert complain(vocabulary, card) == []


def test_one_rule_and_not_two(vocabulary) -> None:
    """
    The hand-written static check now says only what the metadata cannot: what
    `self` reaches, which depends on the kind of card. Everything else is the
    ordinary domain check reading the shape.
    """
    card = {
        "id": "x",
        "name": "X",
        "type": "treasure",
        "expansion": "x",
        "schema_version": "1",
        "statics": [{"stat": "atack", "amount": 1, "scope": "controller"}],
        "abilities": [
            {"trigger": "on_play", "effects": [{"effect": "gain_coins", "amount": 1}]}
        ],
    }

    assert len(complain(vocabulary, card)) == 1


# ----------------------------------------------------------------------
# 5. And still nothing named
# ----------------------------------------------------------------------


def test_the_page_still_names_no_effect_of_its_own(page: str) -> None:
    can = catalogue()
    allowed = {"self", "group", "player", "value", "card", "kind", "kinds",
               "step", "mode", "cost", "ability", "static", "values"}

    named = sorted(
        one["id"]
        for group in ("effects", "conditions", "targets")
        for one in can[group]
        if one["id"] not in allowed and f'"{one["id"]}"' in page
    )

    assert named == []


def test_every_parameter_anywhere_still_lands_somewhere(can: dict[str, Any]) -> None:
    known = {"form", "group", "advanced", "given", "spelling", "body", "nested"}

    for group in ("effects", "conditions", "targets", "abilities", "statics",
                  "structures"):
        for one in can[group]:
            for field in one["fields"]:
                assert field["shown"] in known, f"{one['id']}.{field['id']}"
