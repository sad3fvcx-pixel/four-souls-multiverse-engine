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

from fsme.content.vocabulary import A_MAPPING
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


# ----------------------------------------------------------------------
# 4. What holds a change, and what it is worth to the person writing one
# ----------------------------------------------------------------------


def test_a_field_of_an_event_is_named_and_never_chosen_from_a_list() -> None:
    """
    Three places ask which value of an event is meant, and not one of them
    offers a set to pick from.

    That is the engine's answer and not an omission. `compost` changes
    `source` on `before_loot_draw`, and nothing proposes that field: it exists
    only once a replacement has written it, so a list of the fields an event
    carries would be a list `compost` is not on.
    """
    vocabulary = engine_vocabulary()
    asking = [
        vocabulary.shapes["modify_event"].params["key"],
        vocabulary.condition_shapes["event_value"].params["key"],
    ]
    worked_out = vocabulary.node_shape("worked_out")
    assert worked_out is not None
    asking.append(worked_out.params["from_event"])

    for parameter in asking:
        assert parameter.kind == "text", parameter.name
        assert parameter.values == (), parameter.name


def test_what_a_promise_owes_is_a_set_of_named_changes() -> None:
    """
    Named, and each one a change — the two halves the desk has to be told.
    """
    changes = engine_vocabulary().shapes["promise"].params["changes"]

    assert changes.kind == A_MAPPING
    assert changes.each_shaped_like == "change"

    # Not a list, and not one change. Both were measured to be wrong: a list
    # refuses every card that has one, and calling the whole mapping a change
    # asks the six operations at the top with nowhere to put the field name.
    assert changes.a_list_of == ""
    assert changes.shaped_like == ""


def test_the_desk_is_told_what_holds_the_changes() -> None:
    """
    Published, so the page draws a map of them without being told which
    effect it belongs to or what its names may be.
    """
    from fsme.lab.desk.capabilities import catalogue

    promise = next(one for one in catalogue()["effects"] if one["id"] == "promise")
    changes = next(one for one in promise["fields"] if one["id"] == "changes")

    assert changes["each_shaped_like"] == "change"
    assert changes["shown"] == "named"
    assert changes["choices"] == [], "the names are the author's, not a list"


@pytest.mark.parametrize("named", sorted(FOUR))
def test_a_shipped_promise_keeps_the_names_it_was_written_with(named: str) -> None:
    """
    The names are free text and stay free text.

    `source` is the one that matters: it is not among the values any event is
    proposed with, so anything deriving the names from the engine would lose
    this card and say nothing.
    """
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

    assert once["abilities"][0]["effects"][0]["changes"] == FOUR[named]["changes"]


def test_a_change_that_cannot_be_written_is_not_quietly_dropped() -> None:
    """
    An empty map where a card said something is the failure this cannot have.

    A promise owing nothing is a promise the engine refuses, so writing one
    would turn a card the author was editing into a card that does not load —
    and the checker would say the card owes no changes, which is at least true.
    """
    card = {
        "id": "probe-empty",
        "name": "Empty",
        "type": "treasure",
        "expansion": "probe",
        "abilities": [
            {
                "trigger": "on_play",
                "effects": [{"effect": "promise", "event": "before_damage"}],
            }
        ],
    }

    problems = check_card(build_card(read_card(card)))

    assert problems, "a promise owing nothing must not pass as written"


# ----------------------------------------------------------------------
# 5. What a promise waits for
# ----------------------------------------------------------------------
#
# `when` is a filter on what the event carries: every pair it names has to be
# what the event carries when promises are kept, and nothing else about the
# event matters. It is open — no list of an event's fields exists, and none is
# asked for — so a name the event does not carry is not a mistake the checker
# can see; it is a promise that never meets its event.
#
# Two things are deliberately not pinned here, because they are not part of
# the contract yet: whether `{"k": null}` meets an event that carries no `k`,
# and whether `1` meets `true`. Both follow from Python's equality today, and
# each is a rules decision of its own.

NOT_WRITTEN = object()
"""A promise that says nothing at all about what it waits for."""


def a_roll_after_promising(when: Any, **carried: Any) -> tuple[int, int]:
    """
    Promise to turn the next roll over, then roll; say what came of it.

    The promise is made by the effect a card makes it with, and kept by the
    runtime that keeps every promise, so what is measured is the real path.
    Returns the roll as the event ended up carrying it, and how many promises
    are still owed afterwards.
    """
    from types import SimpleNamespace

    from conftest import make_runtime, make_state

    from fsme.effects.builtin.replacement import promise
    from fsme.events.event import Event
    from fsme.events.types import EventType

    state = make_state()
    runtime = make_runtime(state)
    asked: dict[str, Any] = {} if when is NOT_WRITTEN else {"when": when}

    promise(
        SimpleNamespace(state=state),
        [],
        event="roll_modified",
        changes={"value": {FLIP: 7}},
        **asked,
    )

    payload = {"sides": 6, "value": 2, "natural": 2, **carried}
    event = runtime._propose(Event(type=EventType.ROLL_MODIFIED, payload=payload))

    return int(event.payload["value"]), len(state.promises)


def test_an_attack_roll_meets_a_promise_about_attack_rolls() -> None:
    assert a_roll_after_promising({"attack": True}, attack=True) == (5, 0)


def test_a_plain_roll_does_not_and_the_promise_is_still_owed() -> None:
    assert a_roll_after_promising({"attack": True}, attack=False) == (2, 1)


@pytest.mark.parametrize(
    "when", (NOT_WRITTEN, {}, None), ids=("not written", "empty", "null")
)
@pytest.mark.parametrize("attack", (True, False), ids=("attack roll", "plain roll"))
def test_a_promise_that_names_nothing_meets_any_event_of_its_kind(
    when: Any, attack: bool
) -> None:
    """
    `null` is made into an empty filter when the promise is made, and an empty
    filter has nothing to tell one roll from another.
    """
    assert a_roll_after_promising(when, attack=attack) == (5, 0)


def test_every_pair_a_promise_names_has_to_be_carried() -> None:
    both = {"attack": True, "sides": 6}
    one_of_them = {"attack": True, "sides": 20}

    assert a_roll_after_promising(both, attack=True) == (5, 0)
    assert a_roll_after_promising(one_of_them, attack=True) == (2, 1)


@pytest.mark.parametrize("attack", (True, False), ids=("attack roll", "plain roll"))
def test_a_name_the_event_does_not_carry_never_meets_it(attack: bool) -> None:
    assert a_roll_after_promising({"atack": True}, attack=attack) == (2, 1)


def test_what_else_the_event_carries_does_not_matter() -> None:
    assert a_roll_after_promising(
        {"attack": True}, attack=True, lucky="yes", bonus=3
    ) == (5, 0)


def a_card_promising(when: Any) -> dict[str, Any]:
    effect: dict[str, Any] = {
        "effect": "promise",
        "event": "roll_modified",
        "changes": {"value": {FLIP: 7}},
        "when": when,
    }

    return {
        "id": "probe-when",
        "name": "When",
        "type": "treasure",
        "expansion": "probe",
        "abilities": [{"trigger": "on_play", "effects": [effect]}],
    }


@pytest.mark.parametrize(
    "when",
    ({"attack": True}, {}, None, {"atack": True}),
    ids=("a field it carries", "empty", "null", "a name it does not carry"),
)
def test_the_checker_asks_only_that_what_it_waits_for_is_a_mapping(when: Any) -> None:
    assert check_card(a_card_promising(when)) == []


@pytest.mark.parametrize(
    "when", ("attack", ["attack"], 1), ids=("a word", "a list", "a number")
)
def test_anything_but_a_mapping_is_refused(when: Any) -> None:
    said = check_card(a_card_promising(when))

    assert len(said) == 1
    assert "effects[0].when: 'promise' takes a set of named values here" in said[0]
