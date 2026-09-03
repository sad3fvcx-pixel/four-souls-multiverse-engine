"""
A card is a composition, and the editor is told so by the metadata.

Every card the game ships is one card file with several parts in it: rules that
fire at different moments, numbers it changes while it is in play, the numbers
printed on its face. The author kit could describe exactly one of those parts —
one ability — and nothing said otherwise, because nothing said what a card was
made of at all.

These tests are about that sentence being said and being true: that the card
shape names the parts, that the parts are lists like every other list in the
language, that each part keeps the names it makes to itself the way the engine
does, and that a part this editor cannot build is said rather than dropped.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from fsme.cards.definition import CardDefinition
from fsme.cards.types import PRINTED_NUMBERS
from fsme.lab.desk.author import build_card, check_card
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.vocabulary import CARD_BODIES, OWN_NAMES, engine_vocabulary

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


def card_shape(can: dict[str, Any]) -> dict[str, Any]:
    return next(one for one in can["cards"] if one["id"] == "card")


def field_of(shape: dict[str, Any], name: str) -> dict[str, Any]:
    return next(f for f in shape["fields"] if f["id"] == name)


def a_card(**written: Any) -> dict[str, Any]:
    """
    A card built the way the page sends one: a node with fields and groups.
    """
    return build_card(
        {
            "set": "demo",
            "card": {
                "id": "card",
                "fields": {"name": "Under Test", "type": "loot", **written},
                "groups": {},
            },
        }
    )


def an_ability(**written: Any) -> dict[str, Any]:
    return {"id": "ability", "fields": written, "groups": {}}


def a_static(**written: Any) -> dict[str, Any]:
    return {"id": "static", "fields": written, "groups": {}}


COIN = {"id": "gain_coins", "fields": {"amount": 1}, "groups": {}}


# ----------------------------------------------------------------------
# 1. A card can contain several abilities
# ----------------------------------------------------------------------


def test_what_a_card_is_made_of_is_read_off_the_card(can: dict[str, Any]) -> None:
    """
    Every field of `CardDefinition`, because that is what `from_data` reads and
    therefore what a card file may say. A part added to a card is a field added
    there, and this widens the moment it is.
    """
    shape = card_shape(can)

    assert {f["id"] for f in shape["fields"]} == {
        field.name for field in fields(CardDefinition)
    }


def test_the_parts_of_a_card_are_lists_of_nodes_like_every_other_list(
    can: dict[str, Any],
) -> None:
    """
    Not a special kind of list. `abilities` is to a card what `effects` is to
    an ability, which is why one renderer draws both.
    """
    shape = card_shape(can)

    assert field_of(shape, "abilities")["a_list_of"] == "ability"
    assert field_of(shape, "statics")["a_list_of"] == "static"
    assert field_of(shape, "abilities")["shown"] == "body"
    assert field_of(shape, "statics")["shown"] == "body"
    assert shape["bodies"] == list(CARD_BODIES)


def test_a_card_may_hold_several_abilities() -> None:
    card = a_card(
        abilities=[
            an_ability(trigger="on_play", effects=[COIN]),
            an_ability(trigger="turn_start", effects=[COIN]),
            an_ability(trigger="turn_end", effects=[COIN]),
        ]
    )

    assert len(card["abilities"]) == 3
    assert check_card(card) == [], check_card(card)


def test_the_order_of_the_abilities_is_the_order_they_were_written_in() -> None:
    """
    A card that says "first this, then that" is not the same card the other way
    round, and nothing here may sort them.
    """
    card = a_card(
        abilities=[
            an_ability(trigger="on_play", description=said, effects=[COIN])
            for said in ("first", "second", "third")
        ]
    )

    assert [one["description"] for one in card["abilities"]] == [
        "first",
        "second",
        "third",
    ]


def test_each_ability_keeps_its_own_trigger_and_its_own_effects() -> None:
    card = a_card(
        abilities=[
            an_ability(
                trigger="on_play",
                effects=[{"id": "gain_coins", "fields": {"amount": 1}}],
            ),
            an_ability(
                trigger="turn_start",
                effects=[{"id": "gain_coins", "fields": {"amount": 7}}],
            ),
        ]
    )

    assert card["abilities"][0]["trigger"] == "on_play"
    assert card["abilities"][1]["trigger"] == "turn_start"
    assert card["abilities"][0]["effects"][0]["amount"] == 1
    assert card["abilities"][1]["effects"][0]["amount"] == 7


# ----------------------------------------------------------------------
# 2. Targets stay with the ability that chose them
# ----------------------------------------------------------------------


def test_what_an_ability_picks_out_is_bound_inside_that_ability() -> None:
    """
    The engine gives every ability a context of its own, so a group bound in
    one is not there for another. Two abilities aiming at "a player somebody
    picks" pick two players, and each one's binding lives beside it.
    """
    aimed = {
        "id": "deal_damage",
        "fields": {"amount": 1},
        "aim": "target_player",
        "aim_fields": {},
        "aim_groups": {},
    }
    card = a_card(
        abilities=[
            an_ability(trigger="on_play", effects=[dict(aimed)]),
            an_ability(trigger="turn_start", effects=[dict(aimed)]),
        ]
    )

    for ability in card["abilities"]:
        assert len(ability["targets"]) == 1, "a binding reached across abilities"
        assert ability["effects"][0]["target"] == ability["targets"][0][
            "target_player"
        ]["as"]

    assert check_card(card) == [], check_card(card)


def test_an_ability_that_picks_the_same_thing_twice_picks_it_once() -> None:
    """
    Inside one ability, still. "Deal 1 damage to a player and steal a cent from
    them" is one player, and that is what sharing a binding means.
    """
    aimed = {
        "id": "deal_damage",
        "fields": {"amount": 1},
        "aim": "target_player",
        "aim_fields": {},
        "aim_groups": {},
    }
    healed = {
        "id": "heal",
        "fields": {"amount": 1},
        "aim": "target_player",
        "aim_fields": {},
        "aim_groups": {},
    }
    card = a_card(
        abilities=[an_ability(trigger="on_play", effects=[aimed, healed])]
    )
    (ability,) = card["abilities"]

    assert len(ability["targets"]) == 1
    assert ability["effects"][0]["target"] == ability["effects"][1]["target"]


# ----------------------------------------------------------------------
# 3. Statics are their own thing
# ----------------------------------------------------------------------


def test_a_static_is_written_out_of_its_own_shape() -> None:
    card = a_card(
        statics=[a_static(stat="attack", amount=1, scope="controller")],
        abilities=[an_ability(trigger="on_play", effects=[COIN])],
    )

    assert card["statics"] == [
        {"stat": "attack", "amount": 1, "scope": "controller"}
    ]
    assert check_card(card) == [], check_card(card)


def test_a_card_may_be_nothing_but_statics() -> None:
    """
    "+1 attack while you control this" is a whole card, and it has no ability
    on it at all.
    """
    card = a_card(statics=[a_static(stat="attack", amount=1)])

    assert card["abilities"] == []
    assert check_card(card) == [], check_card(card)


def test_a_static_says_which_numbers_it_may_change_once_its_scope_is_known(
    can: dict[str, Any],
) -> None:
    """
    The dependent domain the renderer learned in the last phase, now reachable:
    there was no way to make a static before, so nothing ever asked.
    """
    static = next(one for one in can["statics"] if one["id"] == "static")
    stat = field_of(static, "stat")

    assert stat["domain_from"] == "scope"
    assert stat["domains"], "a static's stats depend on its scope and nothing said"


def test_a_static_cannot_pick_anything_out_and_the_page_says_so(
    page: str,
) -> None:
    """
    Nothing in a static chooses anybody — it has nowhere to keep a chosen group
    — so a question naming one has, there, no answer it could be given. Said,
    never drawn as a box that takes an answer nothing will read.
    """
    from fsme.lab.desk.author import _chooses

    shapes = engine_vocabulary().node_shapes

    assert _chooses(shapes["ability"]) == "targets"
    assert _chooses(shapes["static"]) == ""
    assert "cannotChooseHtml" in page
    assert "canChoose" in page


# ----------------------------------------------------------------------
# 4. Names do not leak between the parts of a card
# ----------------------------------------------------------------------


def test_the_parts_that_keep_their_names_to_themselves_say_so(
    can: dict[str, Any],
) -> None:
    """
    Published, so that a form can scope what it offers the way the engine
    scopes what it resolves. `Runtime` builds one `AbilityContext` per ability
    and contexts share nothing.
    """
    published = {
        one["id"]: one["own_names"]
        for group in ("cards", "abilities", "statics", "structures")
        for one in can[group]
    }

    assert {name for name, own in published.items() if own} == set(OWN_NAMES)
    assert published["mode"] is False, "a mode runs in its ability's own context"
    assert published["card"] is False, "a card resolves nothing itself"


def test_a_value_one_ability_stores_is_not_a_value_another_may_read() -> None:
    """
    Ability A rolls a die and keeps it; ability B asks whether it equals
    something. At run time B's context has never heard of it, so the comparison
    is a comparison of nothing — which is a card that quietly plays wrong, and
    is refused instead.
    """
    card = a_card(
        abilities=[
            an_ability(
                trigger="on_play",
                effects=[{"id": "roll_dice", "fields": {}}],
            ),
            an_ability(
                trigger="turn_start",
                conditions=[{"id": "values_equal", "fields": {"of": "dice"}}],
                effects=[COIN],
            ),
        ]
    )
    problems = check_card(card)

    assert problems, "a name reached across abilities and nothing said"
    assert "dice" in problems[0]


def test_the_same_ability_may_read_what_it_stored_itself() -> None:
    card = a_card(
        abilities=[
            an_ability(
                trigger="on_play",
                effects=[
                    {"id": "roll_dice", "fields": {"store": "first"}},
                    {"id": "roll_dice", "fields": {"store": "second"}},
                    {
                        "id": "if",
                        "fields": {
                            "if": [
                                {
                                    "id": "values_equal",
                                    "fields": {"of": ["first", "second"]},
                                }
                            ],
                            "then": [COIN],
                        },
                    },
                ],
            )
        ]
    )

    assert check_card(card) == [], check_card(card)


def test_the_page_asks_which_part_of_the_card_is_asking(page: str) -> None:
    """
    The renderer offers stored names by walking one part of the card, not all
    of it, and which parts those are is read off the metadata rather than
    named in the page.
    """
    assert "function definedNames(kind, path)" in page
    assert "walk(partAt(path).node)" in page
    assert "own_names" in page
    assert "state.ability" not in page, "the page still thinks a card has one"


# ----------------------------------------------------------------------
# 5. The printed numbers, and nothing invented
# ----------------------------------------------------------------------


def test_a_number_no_card_of_this_kind_prints_is_not_written(
    can: dict[str, Any],
) -> None:
    """
    A loot card has no hit points. Said with `unless`, which is already the
    language's word for a question another answer has settled — so the form
    greys it out and the card does not carry it.
    """
    shape = card_shape(can)

    assert field_of(shape, "health")["unless"] == "type"
    assert "loot" in field_of(shape, "health")["unless_when"]
    assert "monster" not in field_of(shape, "health")["unless_when"]

    card = a_card(health=9, abilities=[an_ability(trigger="on_play", effects=[COIN])])

    assert "health" not in card


def test_a_number_a_card_of_this_kind_does_print_is_kept() -> None:
    card = build_card(
        {
            "set": "demo",
            "card": {
                "id": "card",
                "fields": {
                    "name": "Big One",
                    "type": "monster",
                    "health": 6,
                    "attack": 2,
                    "roll": 4,
                    "abilities": [an_ability(trigger="on_play", effects=[COIN])],
                },
                "groups": {},
            },
        }
    )

    assert (card["health"], card["attack"], card["roll"]) == (6, 2, 4)
    assert check_card(card) == [], check_card(card)


def test_the_printed_numbers_claim_nothing_about_a_kind_nobody_described(
    can: dict[str, Any],
) -> None:
    """
    Six kinds of card have been described and the engine knows twelve. Silence
    about `starting_item` is silence, not a claim that it has no cost.
    """
    shape = card_shape(can)
    said = set(field_of(shape, "cost")["unless_when"])

    assert said <= {str(kind) for kind in PRINTED_NUMBERS}
    assert "starting_item" not in said


# ----------------------------------------------------------------------
# 6. Nothing is quietly left out
# ----------------------------------------------------------------------


def test_every_field_a_card_may_carry_reaches_a_control(
    can: dict[str, Any], page: str
) -> None:
    """
    The rule the effects already follow. A field the engine reads and the form
    omits is a capability quietly taken away, and the one thing the form asks
    in its own words instead is the card's name.
    """
    drawable = {"form", "group", "advanced", "given", "spelling", "body", "nested"}
    shape = card_shape(can)

    for field in shape["fields"]:
        assert field["shown"] in drawable, field["id"]

    # Every one of them is still reachable — what changed is *when* it is
    # asked, which the shape says and the form obeys. A field the engine reads
    # and the form omits would be a capability quietly taken away; a field
    # behind one click is not.
    asked = {field["id"]: field["asked"] for field in shape["fields"]}

    assert asked["abilities"] == "first"
    assert asked["statics"] == "first"
    assert asked["health"] == "more"
    assert asked["tags"] == "deeper"
    # The two the engine writes for itself are not questions at all.
    assert asked["id"] == "never"
    assert asked["expansion"] == "never"

    featured = page.split("const FEATURED = [")[1].split("]")[0]

    assert '"name"' in featured


def test_a_kind_of_node_the_page_cannot_draw_is_said_rather_than_boxed(
    page: str,
) -> None:
    assert "cannot build one yet" in page
    assert "this editor cannot build it yet" in page


def test_the_page_looks_a_node_kind_up_rather_than_listing_the_ones_it_knows(
    page: str,
) -> None:
    """
    `ability` and `static` are not named in the renderer anywhere. A list of
    them is a list of nodes of a named shape, which is what `mode` already was,
    so the three of them go through the same lookup.
    """
    assert "function kindOf(kind)" in page
    assert "shapeNamed(kind)" in page
    assert 'kind === "mode"' not in page
    assert 'named(can.abilities' not in page


# ----------------------------------------------------------------------
# 7. Cards written the old way still build
# ----------------------------------------------------------------------


def test_a_card_sent_the_way_the_old_page_sent_one_still_builds() -> None:
    """
    One ability at the top with the card's few facts beside it. A page that has
    not been reloaded is not a mistake.
    """
    card = build_card(
        {
            "set": "demo",
            "name": "Old Style",
            "kind": "monster",
            "text": "Gain 1¢.",
            "numbers": {"health": 4},
            "ability": {"trigger": "on_play", "effects": [COIN]},
        }
    )

    assert card["type"] == "monster"
    assert card["health"] == 4
    assert card["metadata"] == {"text": "Gain 1¢."}
    assert len(card["abilities"]) == 1
    assert check_card(card) == [], check_card(card)


def test_a_single_ability_card_is_written_exactly_as_it_was_before() -> None:
    """
    The same card, sent both ways, is the same card. Nothing about a card with
    one ability changed when cards learned to have several.
    """
    both = COIN
    old = build_card(
        {
            "set": "demo",
            "name": "Same",
            "kind": "loot",
            "ability": {"trigger": "on_play", "effects": [both]},
        }
    )
    new = a_card(
        name="Same", abilities=[an_ability(trigger="on_play", effects=[both])]
    )

    assert old == new
