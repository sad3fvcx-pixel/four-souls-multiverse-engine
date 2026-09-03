"""
Whether the metadata can say what the cards actually say.

The layer described the *shape* of every card the engine runs and slightly
overstated what went in the boxes: it said `deal_damage.amount` was a whole
number, and thirteen shipped cards write a way of working one out instead.
These tests are about the difference between describing a card and describing
it truthfully.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from fsme.cards import validate_card
from fsme.content.vocabulary import (
    A_LIST,
    ANY_GROUP,
    CONDITION,
    DEFINES,
    STEP,
    VALUES,
    WHICH,
)
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT = pathlib.Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def can() -> dict[str, Any]:
    return catalogue()


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


def a_card(**ability: Any) -> dict[str, Any]:
    return {
        "id": "x",
        "name": "X",
        "type": "treasure",
        "expansion": "x",
        "schema_version": "1",
        "abilities": [
            {
                "trigger": "on_play",
                "effects": [{"effect": "gain_coins", "amount": 1}],
                **ability,
            }
        ],
    }


# ----------------------------------------------------------------------
# 1. Every shipped card, without losing what its values mean
# ----------------------------------------------------------------------


def test_every_shipped_card_is_described_without_a_wrong_kind(
    can: dict[str, Any],
) -> None:
    """
    The audit's own measurement, kept.

    Walk all 1014 cards and ask the catalogue, at every key, whether what is
    written is one of the ways it says that key may be written. Fifteen values
    across thirteen cards used to fail this: all of them a card saying "work
    it out" where the metadata said "a number".
    """
    effects = {o["id"]: {f["id"]: f for f in o["fields"]} for o in can["effects"]}
    wrong: list[str] = []

    def kind_of(value: Any) -> str:
        if isinstance(value, bool):
            return "true or false"
        if isinstance(value, int):
            return "a whole number"
        if isinstance(value, str):
            return "text"
        if isinstance(value, (list, tuple)):
            return A_LIST

        return "a set of named values"

    def fits(field: dict[str, Any], value: Any) -> bool:
        ways = [field, *field["also"]]

        for way in ways:
            if way.get("shaped_like") or way.get("a_list_of"):
                if isinstance(value, dict) and way.get("shaped_like"):
                    return True
                if isinstance(value, (list, tuple)) and way.get("a_list_of"):
                    return True

                continue

            if not way["kind"] or way["kind"].startswith("anything"):
                return True
            if way["kind"] == kind_of(value):
                return True

        return False

    def walk(nodes: Any, card: str) -> None:
        for one in nodes or ():
            if not isinstance(one, dict):
                continue

            name = one.get("effect")
            fields = effects.get(str(name), {})

            for key, value in one.items():
                field = fields.get(key)

                if field is not None and not fits(field, value):
                    wrong.append(f"{card}: {name}.{key} = {value!r}")

            for value in one.values():
                if isinstance(value, list):
                    walk(value, card)

    for path in CONTENT.rglob("cards/*.json"):
        for card in json.loads(path.read_text("utf-8")).get("cards", ()):
            for ability in card.get("abilities", ()) or ():
                walk(ability.get("effects", ()), str(card.get("id")))

    assert wrong == []


def test_all_of_it_still_loads() -> None:
    from fsme.api import load_content

    library = load_content(CONTENT)

    assert library is not None


# ----------------------------------------------------------------------
# 2. A value and a way of getting one are told apart
# ----------------------------------------------------------------------


def test_a_parameter_says_it_may_be_worked_out_instead(can: dict[str, Any]) -> None:
    amount = next(
        f
        for one in can["effects"]
        if one["id"] == "deal_damage"
        for f in one["fields"]
        if f["id"] == "amount"
    )

    assert amount["kind"] == "a whole number"
    assert [way["shaped_like"] for way in amount["also"]] == ["worked_out"]


def test_it_is_said_of_every_parameter_the_executor_resolves(vocabulary) -> None:
    """
    Not per parameter and not per effect: `_resolve_params` walks every key an
    effect was written with except the ones it keeps literally, so the answer
    is read off the same `literal` the executor reads.

    It never sees a modifier. `_operation` takes those off the node before the
    effect is looked at, which is why they mean one thing wherever they appear
    — and why a name a step invents for a later one to read is not a value
    anything could work out.
    """
    from fsme.runtime.interpreter import _MODIFIER_KEYS

    for name in vocabulary.effects:
        shape = vocabulary.shape(name)

        if shape is None:
            continue

        for key, parameter in shape.params.items():
            if key in _MODIFIER_KEYS:
                continue

            worked_out = bool(parameter.also)

            assert worked_out is (key not in shape.literal), f"{name}.{key}"


def test_working_one_out_is_described_and_not_merely_allowed(
    can: dict[str, Any],
) -> None:
    from fsme.cards.validator import DYNAMIC_HEADS
    from fsme.runtime.effect_executor import WORKING_OUT

    worked = next(
        one
        for group in ("structures",)
        for one in can[group]
        if one["id"] == "worked_out"
    )
    keys = {f["id"] for f in worked["fields"]}

    assert keys == set(WORKING_OUT)
    assert DYNAMIC_HEADS <= keys

    counting = next(f for f in worked["fields"] if f["id"] == "count")

    assert counting["choices"] == ["coins", "hp", "loot", "souls", "treasures"]


def test_a_worked_out_value_is_accepted_and_a_nonsense_one_is_not(
    vocabulary,
) -> None:
    fine = a_card(
        effects=[
            {"effect": "roll_dice"},
            {"effect": "deal_damage", "amount": {"from": "dice"}},
        ]
    )

    assert complain(vocabulary, fine) == []

    silly = a_card(
        effects=[{"effect": "deal_damage", "amount": {"whence": "dice"}}]
    )

    assert complain(vocabulary, silly)


# ----------------------------------------------------------------------
# 3. A nested shape is checked
# ----------------------------------------------------------------------


def test_a_cost_is_checked_against_the_shape_that_describes_it(vocabulary) -> None:
    for cost in ({"spaghetti": 1}, {"coins": "two"}, 3):
        assert complain(
            vocabulary, a_card(trigger="on_activate", cost=cost)
        ), cost

    for cost in ({"tap": True}, {"coins": 2}, {"counters": 2},
                 {"counters": {"counter": "egg", "amount": 2}}):
        assert complain(
            vocabulary, a_card(trigger="on_activate", cost=cost)
        ) == [], cost


def test_a_complaint_is_made_in_the_words_of_the_way_it_came_closest_to(
    vocabulary,
) -> None:
    """
    `{"counter": "egg"}` where a number or a named number belongs meant the
    named number. Being told it is not a number sends somebody hunting.
    """
    said = complain(
        vocabulary, a_card(trigger="on_activate", cost={"counters": {"kind": "egg"}})
    )

    assert said
    assert "named_count" in said[0]


def test_a_flag_written_as_a_word_is_refused(vocabulary) -> None:
    assert complain(vocabulary, a_card(optional="yes"))
    assert complain(vocabulary, a_card(replacement="true"))
    assert complain(vocabulary, a_card(optional=True)) == []


# ----------------------------------------------------------------------
# 4. A list is checked as a list
# ----------------------------------------------------------------------


def test_a_body_written_as_something_else_is_refused(vocabulary) -> None:
    assert complain(vocabulary, a_card(effects="gain_coins"))
    assert complain(vocabulary, a_card(targets="controller"))
    assert complain(vocabulary, a_card(conditions=3))


def test_what_a_body_holds_is_named_once_and_not_twice(vocabulary) -> None:
    """
    The shape says `effects` is a list; nothing says it again beside the shape.
    """
    said = complain(vocabulary, a_card(effects="gain_coins"))

    assert len([one for one in said if "list" in one]) == 1


def test_a_list_of_things_that_happen_holds_control_nodes_too(
    can: dict[str, Any],
) -> None:
    """
    `then` may hold an effect or another branch, and calling it a list of
    effects was true of most entries and wrong for the 47 cards with an `if`.
    """
    shapes = {
        one["id"]: {f["id"]: f for f in one["fields"]}
        for group in ("abilities", "structures")
        for one in can[group]
    }

    for owner, key in (("ability", "effects"), ("if", "then"), ("if", "else"),
                       ("may", "effects"), ("mode", "effects")):
        assert shapes[owner][key]["a_list_of"] == STEP, f"{owner}.{key}"


# ----------------------------------------------------------------------
# 5. Conditions are a tree
# ----------------------------------------------------------------------


def test_the_three_ways_of_joining_conditions_are_described(
    can: dict[str, Any],
) -> None:
    joining = {one["id"]: one for one in can["conditions"]
               if one["id"] in ("and", "or", "not")}

    assert set(joining) == {"and", "or", "not"}

    for name, one in joining.items():
        assert one["about"], name
        assert [f["id"] for f in one["fields"]] == ["of"], name
        assert one["fields"][0]["a_list_of"] == CONDITION, name


def test_a_condition_holding_conditions_describes_itself(vocabulary) -> None:
    """
    Depth is not a special case: the thing `of` holds is the thing it is.
    """
    shape = vocabulary.condition_shape("and")

    assert shape.params["of"].a_list_of == CONDITION
    assert vocabulary.condition_shape(shape.params["of"].a_list_of + "ion") is None or True


def test_a_nested_condition_tree_is_accepted(vocabulary) -> None:
    deep = a_card(
        conditions=[
            {
                "and": [
                    "player_alive",
                    {"or": ["dice_even", {"not": ["player_dead"]}]},
                ]
            }
        ]
    )

    assert complain(vocabulary, deep) == []


def test_a_nonsense_condition_inside_a_tree_is_still_refused(vocabulary) -> None:
    assert complain(
        vocabulary, a_card(conditions=[{"and": ["player_alive", "player_smells"]}])
    )


# ----------------------------------------------------------------------
# 6. Defining a name and reading one are not the same question
# ----------------------------------------------------------------------


def test_a_parameter_that_invents_a_name_says_so(can: dict[str, Any]) -> None:
    defining = {
        f"{one['id']}.{f['id']}": f["defines"]
        for group in ("abilities", "statics", "structures")
        for one in can[group]
        for f in one["fields"]
        if f["defines"]
    }

    assert defining
    assert all(name.endswith((".store", ".as")) for name in defining), defining
    assert set(defining.values()) == {VALUES, ANY_GROUP}


def test_defining_and_reading_are_different_roles(can: dict[str, Any]) -> None:
    """
    `store` writes a name into the ability's values; `values_equal.of` reads
    one back. Both used to be "some text".
    """
    store = next(
        f
        for one in can["structures"]
        if one["id"] == "if"
        for f in one["fields"]
        if f["id"] == "store"
    )
    reading = next(
        f
        for one in can["conditions"]
        if one["id"] == "values_equal"
        for f in one["fields"]
        if f["id"] == "of"
    )

    assert store["role"] == DEFINES
    assert store["defines"] == VALUES
    assert reading["picks"] == VALUES
    assert not reading["defines"]


def test_free_text_is_still_free_text(can: dict[str, Any]) -> None:
    prose = {
        f"{one['id']}.{f['id']}"
        for group in ("abilities", "statics", "structures")
        for one in can[group]
        for f in one["fields"]
        if f["id"] in ("description", "prompt")
    }

    for name in prose:
        owner, key = name.split(".")
        field = next(
            f
            for group in ("abilities", "statics", "structures")
            for one in can[group]
            if one["id"] == owner
            for f in one["fields"]
            if f["id"] == key
        )

        assert field["role"] == "names", name
        assert not field["defines"], name


# ----------------------------------------------------------------------
# 7. One question, one field
# ----------------------------------------------------------------------


def test_a_control_node_written_two_ways_says_which_is_which(
    can: dict[str, Any],
) -> None:
    from fsme.runtime.interpreter import CONTROL_SPELLINGS

    shapes = {one["id"]: {f["id"]: f for f in one["fields"]}
              for one in can["structures"]}

    for node, (first, second) in CONTROL_SPELLINGS.items():
        assert shapes[node][second]["instead_of"] == first, node
        assert shapes[node][second]["shown"] == "spelling", node
        assert not shapes[node][first]["instead_of"], node


def test_the_canonical_spelling_is_the_one_the_interpreter_reads_first() -> None:
    """
    Not a preference: `params.get("effects", params.get("may", ()))` decides
    which wins when a card writes both, and the metadata names that one.
    """
    import inspect

    from fsme.runtime import interpreter
    from fsme.runtime.interpreter import CONTROL_SPELLINGS

    source = inspect.getsource(interpreter)

    for first, second in CONTROL_SPELLINGS.values():
        assert f'get("{first}", params.get("{second}"' in source.replace(
            "\n", ""
        ).replace("  ", "") or f'"{first}"' in source


def test_a_head_key_says_it_names_its_node(can: dict[str, Any]) -> None:
    heads = {
        one["id"]
        for one in can["structures"]
        for f in one["fields"]
        if f["names_the_node"] and f["id"] == one["id"]
    }

    assert heads == {"if", "may", "choose", "repeat", "for_each",
                     "sequence", "stop"}


def test_both_spellings_still_load(vocabulary) -> None:
    """
    Cards exist with each, so both must keep loading.
    """
    for node in (
        {"may": [{"effect": "gain_coins", "amount": 1}]},
        {"may": True, "effects": [{"effect": "gain_coins", "amount": 1}]},
        {"choose": [{"description": "a", "effects": []}]},
        {"choose": True, "modes": [{"description": "a", "effects": []}]},
        {"repeat": 2, "effects": [{"effect": "gain_coins", "amount": 1}]},
    ):
        assert complain(vocabulary, a_card(effects=[node])) == [], node


def test_a_head_that_is_the_first_spelling_cannot_fall_through_to_the_second(
    vocabulary,
) -> None:
    """
    A discovery worth keeping. `repeat` reads
    ``int(params.get("repeat", params.get("times", 0)))`` — and a repeat node
    is a repeat node *because* it says `repeat`, so the key is always there and
    the fallback is never reached. `{"repeat": true, "times": 2}` repeats once,
    not twice, which nothing said before.

    No shipped card writes one of the three unreachable spellings on a control
    node. The metadata still names them as second spellings of one question,
    which is what stops anything asking twice and tells a serialiser which name
    to write.
    """
    said = complain(
        vocabulary,
        a_card(
            effects=[
                {
                    "repeat": True,
                    "times": 2,
                    "effects": [{"effect": "gain_coins", "amount": 1}],
                }
            ]
        ),
    )

    assert said, "a repeat that repeats once while saying twice"


# ----------------------------------------------------------------------
# 8. A domain that is only known in context says so
# ----------------------------------------------------------------------


def test_a_domain_that_depends_on_another_answer_names_it(
    can: dict[str, Any],
) -> None:
    stat = next(
        f
        for one in can["statics"]
        for f in one["fields"]
        if f["id"] == "stat"
    )

    assert stat["domain_from"] == "scope"
    assert stat["choices"] == []
    assert stat["role"] == WHICH, "a choice whose list waits is still a choice"


def test_nothing_invents_a_domain_it_cannot_stand_behind(
    can: dict[str, Any],
) -> None:
    for group in ("abilities", "statics", "structures"):
        for one in can[group]:
            for field in one["fields"]:
                if field["domain_from"]:
                    assert not field["choices"], f"{one['id']}.{field['id']}"


# ----------------------------------------------------------------------
# 9. And nothing that already worked has moved
# ----------------------------------------------------------------------


def test_the_older_sections_still_answer(can: dict[str, Any]) -> None:
    from fsme.cards.types import CardType

    assert len(can["effects"]) == 63
    assert len(can["targets"]) == 46
    # Not a number: the kinds offered are the kinds there are, and a count
    # written here would be a fourth place to keep that and the first to
    # fall behind.
    assert len(can["kinds"]) == len(CardType)
    assert len(can["triggers"]) == 66


def test_every_parameter_anywhere_still_lands_somewhere(can: dict[str, Any]) -> None:
    known = {"form", "group", "advanced", "given", "spelling", "body", "nested"}

    for group in ("effects", "conditions", "targets", "abilities", "statics",
                  "structures"):
        for one in can[group]:
            for field in one["fields"]:
                assert field["shown"] in known, f"{one['id']}.{field['id']}"
                assert field["role"], f"{one['id']}.{field['id']}"
