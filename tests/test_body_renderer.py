"""
The renderer learning the language the metadata now describes.

Three primitives arrived: a body (a list of nodes of a known kind), a nested
shape (one node of a named one), and the ability skeleton drawn from the
ability's own shape. None of them knows the name of an effect, a condition, a
target or a control node — what they know is the four kinds the metadata says
a list may be of, and where each kind is described.

The page is JavaScript, so what is tested is the two halves it sits between:
the metadata it reads, and the card it produces.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from fsme.lab.desk.author import build_card, check_card
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.interpreter import CONTROL_NAMES

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


def a_card(ability: dict[str, Any]) -> dict[str, Any]:
    return build_card(
        {"set": "demo", "name": "Under Test", "kind": "loot", "ability": ability}
    )


def written(ability: dict[str, Any]) -> dict[str, Any]:
    card = a_card(ability)

    assert check_card(card) == [], check_card(card)

    return card["abilities"][0]


COIN = {"id": "gain_coins", "fields": {"amount": 1}}


# ----------------------------------------------------------------------
# 1. An ability is a structure the renderer can draw
# ----------------------------------------------------------------------


def test_the_ability_shape_reaches_the_page(can: dict[str, Any]) -> None:
    shape = next(one for one in can["abilities"] if one["id"] == "ability")
    fields = {f["id"]: f for f in shape["fields"]}

    assert set(fields) == {
        "trigger", "scope", "zone", "optional", "replacement",
        "cost", "conditions", "targets", "effects", "description",
    }


def test_every_ability_field_lands_on_a_control_the_page_has(
    can: dict[str, Any], page: str
) -> None:
    """
    The skeleton is drawn by the ordinary field renderer, so every one of its
    fields has to be somewhere that renderer dispatches to.
    """
    drawn = declared(page)
    shape = next(one for one in can["abilities"] if one["id"] == "ability")

    for field in shape["fields"]:
        assert field["shown"] in drawn, field["id"]

    for where in ("body", "nested"):
        assert f'f.shown === "{where}"' in page


def test_the_page_draws_the_skeleton_from_the_shape_and_not_from_a_list(
    page: str,
) -> None:
    assert "function cardHtml()" in page
    assert 'named(can.cards, "card")' in page
    # An ability is drawn wherever a list of abilities is drawn, which is the
    # same list renderer everything else goes through — so the page names it
    # nowhere. The only field names it mentions are the ones the form above
    # asks in its own words, and there are very few of them.
    featured = page.split("const FEATURED = [")[1].split("]")[0]

    assert featured.count(",") < 3, f"the form is featuring fields by name: {featured}"
    assert '"name"' in featured
    assert '"ability"' not in page.split("<script>")[1]


def test_an_ability_with_the_rest_of_itself_filled_in() -> None:
    ability = written(
        {
            "trigger": "on_activate",
            "scope": "controller",
            "optional": True,
            "cost": {"coins": 2, "tap": True},
            "conditions": [{"id": "player_alive", "fields": {}}],
            "effects": [COIN],
        }
    )

    assert ability["scope"] == "controller"
    assert ability["optional"] is True
    assert ability["cost"] == {"tap": True, "coins": 2}
    assert ability["conditions"] == ["player_alive"]


# ----------------------------------------------------------------------
# 2. A body is a list, and a list keeps its order
# ----------------------------------------------------------------------


def test_the_page_has_one_body_renderer_and_it_is_generic(page: str) -> None:
    assert "function bodyHtml(kind, list, path)" in page
    assert "function nodeHtml(kind, node, path)" in page
    # The three kinds a node is *chosen* from a list for. Anything else the
    # metadata says a list may be of is one named shape, found by that name —
    # which is what a mode always was and what an ability and a static are too.
    for kind in ("step", "condition", "target"):
        assert f"{kind}:" in page.split("const KINDS = {")[1][:400]

    assert "function kindOf(kind)" in page
    assert "shapeNamed(kind)" in page


def test_a_body_keeps_the_order_it_was_given() -> None:
    ability = written(
        {
            "trigger": "on_play",
            "effects": [
                {"id": "roll_dice", "fields": {"sides": 6}},
                {"id": "gain_coins", "fields": {"amount": 1}},
                {"id": "lose_coins", "fields": {"amount": 2}},
            ],
        }
    )

    assert [one["effect"] for one in ability["effects"]] == [
        "roll_dice",
        "gain_coins",
        "lose_coins",
    ]


def test_the_page_can_add_remove_and_reorder(page: str) -> None:
    for name in ("addNode", "dropNode", "moveNode", "setNode"):
        assert f"function {name}(" in page


def test_a_body_inside_a_body_is_the_same_body() -> None:
    """
    A branch's `then` is a list of things that happen, and so is the ability's
    own list. One component draws both, which is what makes depth free.
    """
    ability = written(
        {
            "trigger": "on_play",
            "effects": [
                {
                    "id": "if",
                    "fields": {
                        "if": [{"id": "player_alive", "fields": {}}],
                        "then": [
                            {
                                "id": "if",
                                "fields": {
                                    "if": [{"id": "dice_even", "fields": {}}],
                                    "then": [COIN],
                                },
                            }
                        ],
                    },
                }
            ],
        }
    )
    outer = ability["effects"][0]

    assert outer["if"] == ["player_alive"]
    assert outer["then"][0]["if"] == ["dice_even"]
    assert outer["then"][0]["then"] == [{"effect": "gain_coins", "amount": 1}]


def test_a_body_of_conditions_and_a_body_of_targets_are_the_same_component(
    page: str,
) -> None:
    assert page.count("function bodyHtml(") == 1


# ----------------------------------------------------------------------
# 3. A nested shape is drawn by asking the metadata what is in it
# ----------------------------------------------------------------------


def test_the_page_asks_the_metadata_what_a_cost_holds(page: str) -> None:
    assert "function nestedHtml(field, values, path)" in page
    assert "field.shaped_like" in page
    assert "cost" not in page.split("function nestedHtml")[1][:400]


def test_a_cost_is_written_out_of_its_own_shape() -> None:
    ability = written(
        {
            "trigger": "on_activate",
            "cost": {"counters": {"counter": "egg", "amount": 2}},
            "effects": [COIN],
        }
    )

    assert ability["cost"] == {"counters": {"counter": "egg", "amount": 2}}


def test_a_mode_is_a_nested_shape_inside_a_body() -> None:
    ability = written(
        {
            "trigger": "on_play",
            "effects": [
                {
                    "id": "choose",
                    "fields": {
                        "modes": [
                            {"fields": {"description": "A cent", "effects": [COIN]}},
                            {
                                "fields": {
                                    "description": "Two cents",
                                    "effects": [
                                        {"id": "gain_coins", "fields": {"amount": 2}}
                                    ],
                                }
                            },
                        ]
                    },
                }
            ],
        }
    )
    modes = ability["effects"][0]["modes"]

    assert [one["description"] for one in modes] == ["A cent", "Two cents"]
    assert modes[1]["effects"] == [{"effect": "gain_coins", "amount": 2}]


# ----------------------------------------------------------------------
# 4. What was already there is unchanged
# ----------------------------------------------------------------------


def test_an_ordinary_effect_still_writes_what_it_always_did() -> None:
    ability = written({"trigger": "on_play", "effects": [COIN]})

    assert ability == {
        "trigger": "on_play",
        "effects": [{"effect": "gain_coins", "amount": 1}],
    }


def test_aiming_still_binds_a_group_and_points_at_it() -> None:
    ability = written(
        {
            "trigger": "on_play",
            "effects": [
                {
                    "id": "deal_damage",
                    "fields": {"amount": 1},
                    "aim": "target_player",
                    "aim_fields": {"exclude_controller": True},
                }
            ],
        }
    )

    assert ability["effects"][0]["target"] == "chosen_1"
    assert "targets" not in ability
    assert ability["effects"][0]["targets"] == [
        {"target_player": {"exclude_controller": True, "as": "chosen_1"}}
    ]


def test_every_way_a_field_may_be_shown_still_reaches_something(
    page: str, can: dict[str, Any]
) -> None:
    """
    Every `shown` the metadata can produce has to land somewhere in the
    renderer, or a capability disappears without anybody noticing.

    ``given`` is the one that no longer needs a branch of its own: a parameter
    the engine answers is not asked at all now, which is a wider rule than
    ``shown`` was and catches the bound names and the second spellings with it.
    """
    routed = {"spelling", "group", "advanced", "body", "named", "nested",
              "form"}
    possible = {
        field["shown"]
        for group in ("effects", "conditions", "targets", "cards",
                      "abilities", "statics", "structures")
        for one in can[group]
        for field in one["fields"]
    }

    assert possible <= routed | {"given"}, possible - routed - {"given"}

    for where in ("spelling", "group", "advanced"):
        assert f'f.shown === "{where}"' in page, where

    # And the one that replaced the `given` branch, which is what stops an
    # engine-supplied field from ever reaching a box.
    assert 'f.asked === "never"' in page
    assert "function valueHtml(f, values, siblings, path)" in page


def test_the_page_still_names_no_effect_of_its_own() -> None:
    text = PAGE.read_text("utf-8")
    can = catalogue()
    allowed = {"self", "group", "player", "value", "card", "kind", "kinds",
               "step", "mode", "cost", "ability", "static"}

    named = sorted(
        one["id"]
        for group in ("effects", "conditions", "targets")
        for one in can[group]
        if one["id"] not in allowed and f'"{one["id"]}"' in text
    )

    assert named == []


# ----------------------------------------------------------------------
# 5. What cannot be drawn is said, not dropped
# ----------------------------------------------------------------------


def test_the_page_says_when_it_cannot_build_something(page: str) -> None:
    assert "function unsupportedHtml(field)" in page
    assert "the engine can do this" in page
    assert "and this editor cannot build it yet" in page


def test_a_body_of_a_kind_the_page_has_no_component_for_says_so(page: str) -> None:
    assert "const of = kindOf(kind);\n  if (!of) {" in page
    assert "cannot build one yet" in page


def test_whether_a_node_can_be_drawn_is_asked_of_the_metadata(page: str) -> None:
    """
    Not a list of names: a structure the page can draw is one whose every own
    field lands somewhere this renderer has a control for.
    """
    assert "function drawable(node)" in page
    assert "node.fields.every(f => DRAWS.includes(f.shown))" in page


def test_the_metadata_says_which_shapes_are_things_that_happen(
    can: dict[str, Any],
) -> None:
    """
    A cost and a mode are described beside the control nodes and are not steps.
    The page filters on the fact rather than on the names.
    """
    steps = {one["id"] for one in can["structures"] if one["a_step"]}

    assert steps == set(CONTROL_NAMES)
    assert {one["id"] for one in can["structures"] if not one["a_step"]} == {
        "mode",
        "worked_out",
        "named_count",
        "change",
    }


def test_every_control_node_is_offered_and_none_is_half_offered(
    can: dict[str, Any], page: str
) -> None:
    drawn = declared(page)

    for one in can["structures"]:
        if not one["a_step"]:
            continue

        for field in one["fields"]:
            assert field["shown"] in drawn, f"{one['id']}.{field['id']}"


# ----------------------------------------------------------------------
# 6. The card that comes out is the card that always came out
# ----------------------------------------------------------------------


def test_an_unfinished_control_node_is_refused_and_not_saved() -> None:
    for node in ("if", "may", "choose", "repeat", "sequence"):
        card = a_card({"trigger": "on_play", "effects": [{"id": node, "fields": {}}]})

        assert check_card(card), node
        assert "nothing to do" in check_card(card)[0], node


def test_a_control_node_keeps_the_key_that_makes_it_one() -> None:
    """
    A card being built may be unfinished; it may not be a node the engine
    cannot recognise.
    """
    for node, empty in (("if", []), ("may", []), ("repeat", 0),
                        ("for_each", ""), ("stop", True)):
        card = a_card({"trigger": "on_play", "effects": [{"id": node, "fields": {}}]})
        written_node = card["abilities"][0]["effects"][0]

        assert written_node[node] == empty, node


def test_the_card_is_still_ordinary_content(tmp_path: Path) -> None:
    import json

    from fsme.api import load_content

    card = a_card(
        {
            "trigger": "on_play",
            "effects": [
                {
                    "id": "if",
                    "fields": {
                        "if": [{"id": "player_alive", "fields": {}}],
                        "then": [COIN],
                    },
                }
            ],
        }
    )
    where = tmp_path / "demo"
    (where / "cards").mkdir(parents=True)
    (where / "manifest.json").write_text(
        json.dumps({"id": "demo", "name": "Demo", "version": "1.0.0",
                    "schema_version": "1"})
    )
    (where / "cards" / "one.json").write_text(json.dumps({"cards": [card]}))

    library = load_content([tmp_path])

    assert library.registry().get(card["id"]) is not None


# ----------------------------------------------------------------------
# 5. Every way the model says a field may be shown reaches a control
# ----------------------------------------------------------------------


def declared(page: str) -> set[str]:
    """
    The ways of showing a field this page says it has a control for.

    Read from the page rather than written here. It is the page's own claim
    about itself: the model says how a field should be shown, and only the
    client knows whether it can draw that. A second list here would be a
    second answer to a question this file does not get to answer.
    """
    said = page.split("const DRAWS = [")[1].split("]")[0]

    return set(re.findall(r'"(\w+)"', said))


def routed(page: str) -> set[str]:
    """
    The ways the renderer actually branches on.

    Not the same set as ``declared``: a way of being shown may be reached by a
    branch that does not name it, and one of them is.
    """
    return set(re.findall(r'f\.shown === "(\w+)"', page))


def published(can: dict[str, Any]) -> set[str]:
    """
    Every way the model says any field may be shown, anywhere.
    """
    return {
        field["shown"]
        for group in ("effects", "conditions", "targets", "cards",
                      "abilities", "statics", "structures")
        for one in can[group]
        for field in one["fields"]
    }


def test_every_way_a_field_may_be_shown_has_a_control(
    can: dict[str, Any], page: str
) -> None:
    """
    The invariant this file exists to keep.

    `shown` is the model's answer to what kind of question a field is; `DRAWS`
    is the page's answer to which of those it can draw. Neither may be derived
    from the other — a different client would answer the second differently
    while reading the same model — so the only thing that can be checked is
    that they still meet.

    A way of being shown that the engine gains and this page cannot draw fails
    here, which is the whole point: it would otherwise be drawn by the last
    branch in the chain, as a box, and a structure asked for in a box is a
    capability quietly taken away.
    """
    missing = published(can) - declared(page)

    assert missing == set(), f"the page has no control for: {sorted(missing)}"


def test_the_page_claims_no_control_it_does_not_have(
    can: dict[str, Any], page: str
) -> None:
    """
    The other direction, so the claim cannot become a fiction.

    Most ways of being shown are reached by a branch naming them. One is not:
    every field the model shows as `given` is one nobody is asked, and the
    renderer turns those away before it looks at `shown` at all. So a claim
    with no branch of its own is allowed exactly when the model says every
    field of that kind is answered by a branch there is — which is read off
    the model here rather than written down as an exception.
    """
    script = page.split("<script>")[1]
    unbranched = declared(page) - routed(script)
    fields = [
        field
        for group in ("effects", "conditions", "targets", "cards",
                      "abilities", "statics", "structures")
        for one in can[group]
        for field in one["fields"]
    ]

    for way in sorted(unbranched):
        theirs = [f for f in fields if f["shown"] == way]

        assert theirs, f"the page claims {way!r}, and nothing is shown that way"
        assert all(f["asked"] == "never" or f["one_of"] for f in theirs), (
            f"{way!r} has no branch of its own and is not answered by another"
        )


def test_nothing_is_shown_a_way_nobody_publishes(
    can: dict[str, Any], page: str
) -> None:
    """
    A claim for a way of being shown that no longer exists is dead weight, and
    dead weight is what falls out of step first.
    """
    assert declared(page) - published(can) == set()
