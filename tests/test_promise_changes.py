"""
What a promise may change about an event, and who knows it.

The engine has always had six ways to change a value an event carries. They
are declared beside the code that applies them, enforced at the boundary that
takes them from a card, and — until this — described nowhere, so somebody
writing a card had to already know the answer to find it out.

These tests hold the three to one another: what the applier does, what the
boundary accepts, and what the vocabulary says. A seventh operation, or a
sixth described as a fifth, fails here rather than quietly.
"""

from __future__ import annotations

from typing import Any

import pytest

from fsme.effects.errors import EffectExecutionError
from fsme.lab.desk.author import build_card, check_card, read_card
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.state.promises import (
    CAP,
    CHANGES,
    DELTA,
    FACTOR,
    FLIP,
    FLOOR,
    VALUE,
    Promise,
)

# ----------------------------------------------------------------------
# 1. What the engine already does
# ----------------------------------------------------------------------


def test_the_six_ways_to_change_a_value() -> None:
    """
    The set, written down once. Everything below reads it rather than this.
    """
    assert CHANGES == (VALUE, DELTA, FACTOR, CAP, FLOOR, FLIP)


@pytest.mark.parametrize(
    ("change", "carried", "expected"),
    [
        ({VALUE: "discard"}, {"source": "deck"}, "discard"),
        ({DELTA: 2}, {"amount": 1}, 3),
        ({FACTOR: 2}, {"amount": 3}, 6),
        ({CAP: 1}, {"amount": 3}, 1),
        ({CAP: 5}, {"amount": 3}, 3),
        ({FLOOR: 2}, {"amount": 1}, 2),
        ({FLOOR: 2}, {"amount": 4}, 4),
        ({FLIP: 7}, {"amount": 2}, 5),
    ],
)
def test_what_each_change_does(
    change: dict[str, Any], carried: dict[str, Any], expected: Any
) -> None:
    """
    One case each, from the applier rather than from the docstrings.
    """
    key = next(iter(carried))
    promise = Promise(event="before_damage", changes={key: change})

    assert promise.apply_to(carried)[key] == expected


def test_the_changes_compose_in_one_order() -> None:
    """
    Not independent: a number goes through all of them, and which came first
    is behaviour. `value` is the exception and settles the answer outright.
    """
    promise = Promise(
        event="before_damage",
        changes={"amount": {DELTA: 1, FACTOR: 2, CAP: 5}},
    )

    # (3 + 1) * 2 = 8, capped to 5.
    assert promise.apply_to({"amount": 3})["amount"] == 5

    outright = Promise(event="before_damage", changes={"amount": {VALUE: 9, DELTA: 1}})

    assert outright.apply_to({"amount": 3})["amount"] == 9


def test_only_a_number_goes_through_five_of_them() -> None:
    """
    `value` replaces whatever is there; the other five read a number, which is
    what makes them a different question to ask somebody.
    """
    replaced = Promise(event="before_loot_draw", changes={"source": {VALUE: "discard"}})

    assert replaced.apply_to({})["source"] == "discard"

    for change in (DELTA, FACTOR, CAP, FLOOR, FLIP):
        promise = Promise(event="before_damage", changes={"amount": {change: 2}})

        assert isinstance(promise.apply_to({"amount": 1})["amount"], int), change


def test_the_boundary_refuses_anything_that_is_not_one_of_them() -> None:
    """
    The card side, where a name a person invented has to be turned down.
    """
    from fsme.effects.builtin.replacement import promise

    with pytest.raises(EffectExecutionError) as refused:
        promise(None, [], event="before_damage", changes={"amount": {"times": 2}})

    assert "a change is one of" in str(refused.value)

    for change in CHANGES:
        assert change in str(refused.value), change


# ----------------------------------------------------------------------
# 2. What the vocabulary says about it
# ----------------------------------------------------------------------


def test_a_change_is_described() -> None:
    """
    The shape exists and is one of the small ones a card writes inside
    something else, like a cost or a mode.
    """
    shape = engine_vocabulary().node_shape("change")

    assert shape is not None
    assert shape.params


def test_every_change_the_engine_applies_is_described() -> None:
    """
    The one test that stops the description falling behind the applier.

    Read from `CHANGES` rather than listed, so an operation the engine gains
    and nobody describes fails here — and so does a description for an
    operation the engine does not have.
    """
    shape = engine_vocabulary().node_shape("change")
    assert shape is not None

    assert set(shape.params) == set(CHANGES)


def test_each_change_says_what_it_takes_and_what_it_does() -> None:
    """
    A form drawing this asks six questions; each needs a control and a
    sentence, and neither may be guessed from the name.
    """
    shape = engine_vocabulary().node_shape("change")
    assert shape is not None

    for name, parameter in shape.params.items():
        assert parameter.kind, name
        assert parameter.describes, name

    # `value` puts back whatever the event carried, which may not be a number
    # at all — `compost` puts a word there. The other five read a number.
    assert shape.params[VALUE].kind != shape.params[DELTA].kind

    for change in (DELTA, FACTOR, CAP, FLOOR, FLIP):
        assert shape.params[change].kind == shape.params[DELTA].kind, change


def test_nothing_about_a_change_is_required() -> None:
    """
    A change carries one of the six, not all of them, so insisting on any
    would refuse every card that has ever been written.
    """
    shape = engine_vocabulary().node_shape("change")
    assert shape is not None

    assert [name for name, one in shape.params.items() if one.required] == []


def test_the_desk_is_told_what_a_change_is() -> None:
    """
    Published on the same terms as every other small shape, so whatever draws
    one draws this.
    """
    from fsme.lab.desk.capabilities import catalogue

    described = {one["id"]: one for one in catalogue()["structures"]}

    assert "change" in described

    change = described["change"]

    assert change["about"]
    assert not change["a_step"], "a change is not something that happens"
    assert {one["id"] for one in change["fields"]} == set(CHANGES)


# ----------------------------------------------------------------------
# 3. The four cards that use one
# ----------------------------------------------------------------------

FOUR = {
    "compost": {"event": "before_loot_draw", "changes": {"source": {"value": "discard"}}},
    "mom_s_bra": {"event": "before_damage", "changes": {"amount": {"cap": 1}}},
    "two_of_clubs": {
        "event": "before_loot_draw",
        "changes": {"count": {"factor": 2}},
        "unlimited": True,
    },
    "polycephalus": {
        "event": "roll_modified",
        "when": {"attack": True},
        "changes": {"value": {"flip": 7}},
    },
}
"""
The promises the shipped sets contain, as they are written on the cards.

Three of the four use an operation nothing described until now, which is why
they are here: whatever the description says, these four must go on meaning
what they meant.
"""


@pytest.mark.parametrize("named", sorted(FOUR))
def test_a_shipped_promise_still_says_what_it_said(named: str) -> None:
    card = {
        "id": f"probe-{named}",
        "name": named,
        "type": "treasure",
        "expansion": "probe",
        "abilities": [
            {"trigger": "on_play", "effects": [{"effect": "promise", **FOUR[named]}]}
        ],
    }

    said = read_card(card)
    once = build_card(said)

    assert read_card(once) == said, "the card came back meaning something else"
    assert build_card(read_card(once)) == once, "writing it twice wrote two cards"
    assert check_card(once) == []
    assert once["abilities"][0]["effects"][0] == card["abilities"][0]["effects"][0]
