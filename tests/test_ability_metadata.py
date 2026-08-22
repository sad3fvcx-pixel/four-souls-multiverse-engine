"""
What the engine says about the parts of a card that are not effects.

An ability, a static and the seven control nodes have always been described by
`engine_vocabulary()`, and the description never reached anything that could
use it: `catalogue()` returned effects, conditions, targets and triggers, and
every field of every node shape was typed `text` whatever it actually held.

These tests are about the truthfulness of that description. They do not test a
renderer — there is none for an ability yet — they test that a renderer given
this metadata would know what question to ask, which is the whole of what this
layer is for.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

import pytest

from fsme.cards.definition import Ability, Static
from fsme.content.vocabulary import (
    A_LIST,
    A_MAPPING,
    BODY,
    NESTED,
    NODES,
    ROLES,
)
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.interpreter import CONTROL_BODIES, CONTROL_KEYS, CONTROL_NAMES
from fsme.runtime.vocabulary import engine_vocabulary

SECTIONS = ("abilities", "statics", "structures")


@pytest.fixture(scope="module")
def can() -> dict[str, Any]:
    return catalogue()


def shapes(can: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {one["id"]: one for group in SECTIONS for one in can[group]}


def every_field(can: dict[str, Any]):
    for group in SECTIONS:
        for one in can[group]:
            for field in one["fields"]:
                yield one["id"], field


# ----------------------------------------------------------------------
# 1. The shapes reach the metadata at all
# ----------------------------------------------------------------------


def test_the_parts_of_a_card_that_are_not_effects_are_published(
    can: dict[str, Any],
) -> None:
    published = set(shapes(can))

    assert "ability" in published
    assert "static" in published
    assert CONTROL_NAMES <= published, "a control node the engine has and nothing offers"


def test_every_node_shape_the_engine_builds_is_offered(can: dict[str, Any]) -> None:
    """
    The rule the effects already follow: nothing is dropped for being hard to
    draw, because a capability the interface omits is one quietly taken away.
    """
    known = set(engine_vocabulary().node_shapes)

    assert known == set(shapes(can))


def test_a_node_says_where_it_keeps_what_it_does(can: dict[str, Any]) -> None:
    """
    A node with every body empty resolves to nothing and reads exactly like one
    that works. Saying where the bodies are is what lets anything tell.
    """
    published = shapes(can)

    for name, bodies in CONTROL_BODIES.items():
        assert published[name]["bodies"] == list(bodies), name

    assert published["mode"]["bodies"] == ["effects"]
    assert published["ability"]["bodies"] == []


def test_every_node_is_described_in_words(can: dict[str, Any]) -> None:
    for group in SECTIONS:
        for one in can[group]:
            assert one["about"], one["id"]
            assert one["about"] != one["id"].replace("_", " "), one["id"]


def test_an_ability_and_a_static_are_kept_apart(can: dict[str, Any]) -> None:
    """
    A static has no trigger, no effects and nothing that resolves. Publishing
    it as a kind of ability would say a thing about the engine that is not so.
    """
    assert [one["id"] for one in can["statics"]] == ["static"]
    assert "static" not in {one["id"] for one in can["abilities"]}


# ----------------------------------------------------------------------
# 2. The fields say what they really hold
# ----------------------------------------------------------------------


def test_an_ability_field_carries_the_kind_its_annotation_names(
    can: dict[str, Any],
) -> None:
    """
    Derived from the dataclass, the way an effect's parameters are derived from
    its handler's signature. Not a table: a table would drift.
    """
    written = {
        field["id"]: field["kind"]
        for owner, field in every_field(can)
        if owner == "ability"
    }

    assert written == {
        "trigger": "text",
        "conditions": A_LIST,
        "targets": A_LIST,
        "effects": A_LIST,
        "optional": "true or false",
        "cost": A_MAPPING,
        "replacement": "true or false",
        "scope": "text",
        "zone": "text",
        "description": "text",
    }


def test_a_static_field_carries_the_kind_its_annotation_names(
    can: dict[str, Any],
) -> None:
    written = {
        field["id"]: field["kind"]
        for owner, field in every_field(can)
        if owner == "static"
    }

    assert written == {
        "stat": "text",
        "amount": "a whole number",
        "forbids": "text",
        "per_counter": "text",
        "scope": "text",
        "conditions": A_LIST,
        "description": "text",
    }


def test_a_flag_is_a_flag_and_not_a_box(can: dict[str, Any]) -> None:
    """
    `optional` and `replacement` used to be typed text, which is a box a person
    types "true" into and a card the engine reads as true because the string is
    not empty.
    """
    for owner, field in every_field(can):
        if field["id"] in ("optional", "replacement"):
            assert field["kind"] == "true or false", f"{owner}.{field['id']}"
            assert field["role"] == "switch", f"{owner}.{field['id']}"


def test_every_field_of_every_node_has_a_role_the_layer_knows(
    can: dict[str, Any],
) -> None:
    for owner, field in every_field(can):
        assert field["role"] in ROLES, f"{owner}.{field['id']}"


def test_a_domain_the_engine_enforces_is_a_domain_the_metadata_offers(
    can: dict[str, Any],
) -> None:
    """
    Four places where a misspelling used to change what a card did rather than
    stop it: a scope falls through to the branch meaning something else, a zone
    the state does not have makes an ability that never works, an action nobody
    forbids is a prohibition that never catches, and a cost key is refused by
    the payment check and by nothing earlier.
    """
    from fsme.rules.restrictions import ACTIONS
    from fsme.rules.statics import STATIC_SCOPES
    from fsme.runtime.runtime import ABILITY_SCOPES, ABILITY_ZONES

    published = shapes(can)

    def domain(node: str, key: str) -> list[str]:
        return next(
            f["choices"] for f in published[node]["fields"] if f["id"] == key
        )

    assert domain("ability", "scope") == list(ABILITY_SCOPES)
    assert domain("ability", "zone") == list(ABILITY_ZONES)
    assert domain("static", "scope") == list(STATIC_SCOPES)
    assert domain("static", "forbids") == list(ACTIONS)
    assert len(domain("ability", "trigger")) == 66


def test_the_one_domain_that_depends_on_another_answer_is_not_guessed(
    can: dict[str, Any],
) -> None:
    """
    Which stats a static may change depends on what its scope reaches and on
    whether its card is a monster. A domain right half the time is worse than
    none, so none is published until the layer can say "it depends".
    """
    published = shapes(can)
    stat = next(f for f in published["static"]["fields"] if f["id"] == "stat")

    assert stat["choices"] == []


# ----------------------------------------------------------------------
# 3. A list is a list
# ----------------------------------------------------------------------


def test_a_list_of_nodes_says_what_it_is_a_list_of(can: dict[str, Any]) -> None:
    listed = {
        f"{owner}.{field['id']}": field["a_list_of"]
        for owner, field in every_field(can)
        if field["a_list_of"]
    }

    assert listed == {
        "ability.conditions": "condition",
        "ability.targets": "target",
        "ability.effects": "effect",
        "static.conditions": "condition",
        "mode.effects": "effect",
        "if.if": "condition",
        "if.conditions": "condition",
        "if.then": "effect",
        "if.else": "effect",
        "may.may": "effect",
        "may.effects": "effect",
        "choose.choose": "mode",
        "choose.modes": "mode",
        "repeat.effects": "effect",
        "for_each.effects": "effect",
        "sequence.sequence": "effect",
        "sequence.effects": "effect",
    }


def test_a_list_is_never_published_as_text(can: dict[str, Any]) -> None:
    for owner, field in every_field(can):
        if field["a_list_of"]:
            assert field["kind"] == A_LIST, f"{owner}.{field['id']}"
            assert field["role"] == BODY, f"{owner}.{field['id']}"
            assert field["shown"] == "body", f"{owner}.{field['id']}"


def test_a_list_of_nodes_is_not_a_structure(can: dict[str, Any]) -> None:
    """
    The distinction the whole concept exists for. `structure` says the inside
    is not described here; `a_list_of` says it is, and by what.
    """
    for owner, field in every_field(can):
        assert not (
            field["a_list_of"] and field["role"] == "structure"
        ), f"{owner}.{field['id']}"


# ----------------------------------------------------------------------
# 4. A nested shape names a shape
# ----------------------------------------------------------------------


def test_a_nested_field_says_which_shape_it_holds(can: dict[str, Any]) -> None:
    nested = {
        f"{owner}.{field['id']}"
        for owner, field in every_field(can)
        if field["shaped_like"]
    }

    assert "ability.cost" in nested
    assert "for_each.of" in nested
    assert "for_each.for_each" in nested

    for owner, field in every_field(can):
        if field["shaped_like"]:
            assert field["role"] == NESTED, f"{owner}.{field['id']}"
            assert field["shown"] == "nested", f"{owner}.{field['id']}"


def test_every_named_kind_is_one_this_layer_can_answer(can: dict[str, Any]) -> None:
    """
    `a_list_of` and `shaped_like` may only name something the rest of the
    metadata describes — three registries and two node shapes, and no more.
    """
    published = set(shapes(can))
    answerable = {"effect", "condition", "target"} | published

    for owner, field in every_field(can):
        for named in (field["a_list_of"], field["shaped_like"]):
            if not named:
                continue

            assert named in NODES, f"{owner}.{field['id']} names {named!r}"
            assert named in answerable, f"nothing describes {named!r}"


def test_the_cost_shape_is_the_one_the_payment_check_enforces(
    can: dict[str, Any],
) -> None:
    from fsme.rules.costs import KINDS

    cost = shapes(can)["cost"]

    assert {field["id"] for field in cost["fields"]} == set(KINDS)

    kinds = {field["id"]: field["kind"] for field in cost["fields"]}

    assert kinds["tap"] == "true or false"
    assert kinds["coins"] == "a whole number"
    assert kinds["discard"] == "a whole number"
    assert kinds["hp"] == "a whole number"


def test_a_mode_is_a_description_and_a_body(can: dict[str, Any]) -> None:
    mode = shapes(can)["mode"]
    by_name = {field["id"]: field for field in mode["fields"]}

    assert by_name["description"]["required"]
    assert by_name["effects"]["a_list_of"] == "effect"


# ----------------------------------------------------------------------
# 5. What a trigger means by silence
# ----------------------------------------------------------------------


def test_every_trigger_publishes_the_scope_it_defaults_to(
    can: dict[str, Any],
) -> None:
    from fsme.runtime.runtime import ABILITY_SCOPES

    assert len(can["triggers"]) == 66

    for trigger in can["triggers"]:
        assert trigger["scope"] in ABILITY_SCOPES, trigger["id"]


def test_the_published_default_is_the_one_the_engine_would_use() -> None:
    """
    Asked of `ability_scope` rather than written out again, because a list
    written out again is free to drift from the branch that decides.
    """
    from fsme.events import EventType
    from fsme.runtime.runtime import ability_scope

    vocabulary = engine_vocabulary()

    for event in EventType:
        assert vocabulary.trigger_scopes[str(event)] == ability_scope(
            Ability(trigger=str(event))
        ), str(event)


def test_the_triggers_a_card_most_often_uses_are_the_ones_that_look_after_themselves(
    can: dict[str, Any],
) -> None:
    """
    `on_play` and `on_activate` are the two the shipped content leaves unwritten
    — 176 abilities between them — and both default to `self`, which is what
    they mean. Everything else defaults to the whole table.
    """
    by_name = {trigger["id"]: trigger for trigger in can["triggers"]}

    assert by_name["on_play"]["scope"] == "self"
    assert by_name["on_activate"]["scope"] == "self"
    assert by_name["damage_dealt"]["scope"] == "any"
    assert by_name["turn_end"]["scope"] == "any"


def test_publishing_the_default_changes_nothing_a_card_may_write() -> None:
    """
    A metadata exposure and nothing else: an ability with no scope loads
    exactly as it did, because the default is where it always was.
    """
    assert Ability(trigger="damage_dealt").scope is None
    assert Ability.from_data({"trigger": "damage_dealt"}).scope is None


# ----------------------------------------------------------------------
# 6. And nothing that already worked has moved
# ----------------------------------------------------------------------


def test_the_sections_that_were_there_are_still_there(can: dict[str, Any]) -> None:
    assert {"kinds", "triggers", "effects", "conditions", "targets"} <= set(can)
    assert len(can["effects"]) == 63
    assert len(can["conditions"]) == 41
    assert len(can["targets"]) == 46


def test_no_effect_condition_or_target_parameter_gained_a_body(
    can: dict[str, Any],
) -> None:
    """
    The two new concepts describe the ability layer and nothing below it. An
    effect's structured data is still a structure — `watch_for.effects` really
    is a list of effect nodes, and saying so here would change what the form
    already draws, which is a separate decision from this one.
    """
    for group in ("effects", "conditions", "targets"):
        for one in can[group]:
            for field in one["fields"]:
                assert not field["a_list_of"], f"{one['id']}.{field['id']}"
                assert not field["shaped_like"], f"{one['id']}.{field['id']}"
                assert field["shown"] in (
                    "form",
                    "group",
                    "advanced",
                    "given",
                    "spelling",
                ), f"{one['id']}.{field['id']}"


def test_the_node_shapes_still_follow_their_own_dataclasses() -> None:
    """
    Derived, not declared: a field added to the language widens this the moment
    it exists, and a test that reads the dataclass is what keeps it so.
    """
    vocabulary = engine_vocabulary()

    assert set(vocabulary.node_shape("ability").params) == {
        field.name for field in fields(Ability)
    }
    assert set(vocabulary.node_shape("static").params) == {
        field.name for field in fields(Static)
    }

    for name, keys in CONTROL_KEYS.items():
        shape = vocabulary.node_shape(name)

        assert set(keys) <= set(shape.params), name
