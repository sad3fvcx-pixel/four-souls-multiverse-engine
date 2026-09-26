"""
Saying, where a card leaves a question blank, what the engine will read there.

A parameter nobody answers still has an answer. `_ask` takes one thing when the
card does not say how many; `_target_deck_card` searches the loot deck when the
card does not say which; `_card_counters` asks about charge counters when the
card does not name a counter. All of that was written down in exactly one place
— the line that applies it — so the form, which reads the other place, drew
every one of those boxes with "— leave it out —" under it. That is not a small
wording problem: it tells an author that a blank box means *nothing happens*,
when it means *this happens instead*.

So the defaults are now declared beside the lines that apply them, and the
tests here are about the join. The important ones do not name a value at all:
they run the engine twice, once with the parameter left out and once with it
written as whatever the metadata declares, and insist the two are the same
game. A declaration that drifted from its handler fails them without anybody
having to remember which word it was.

What is deliberately *not* declared is in the last section. Three families read
their defaults differently depending on what else the card wrote, and a single
declared value would be wrong for some of the conditions that share it.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from conftest import make_state

from fsme.content.vocabulary import Vocabulary
from fsme.lab.desk.capabilities import catalogue
from fsme.rng.rng import RNG
from fsme.rules.costs import CHARGE
from fsme.runtime.ability_context import AbilityContext
from fsme.runtime.condition_evaluator import THE_USUAL_COUNTER, ConditionEvaluator
from fsme.runtime.errors import DecisionRequired
from fsme.runtime.target_resolver import (
    ONE,
    THE_DECK_ITSELF,
    THE_USUAL_DECK,
    TargetResolver,
)
from fsme.runtime.vocabulary import engine_vocabulary


@pytest.fixture(scope="module")
def vocabulary() -> Vocabulary:
    return engine_vocabulary()


@pytest.fixture(scope="module")
def can() -> dict[str, Any]:
    return catalogue()


def declared(vocabulary: Vocabulary) -> dict[tuple[str, str, str], Any]:
    """
    Every condition and target parameter that now says what a blank means.
    """
    return {
        (family, owner, name): parameter.default
        for family, table in (
            ("condition", vocabulary.condition_shapes),
            ("target", vocabulary.target_shapes),
        )
        for owner, shape in table.items()
        for name, parameter in shape.params.items()
        if parameter.default is not None
    }


# ------------------------------------------------------------ what is declared


def test_the_declared_defaults_are_the_ones_this_stage_measured(
    vocabulary: Vocabulary,
) -> None:
    """
    Not a sample. Adding a default to a condition or a target without measuring
    what its handler does is the mistake this whole stage exists to undo, so a
    new one fails here until somebody has looked.
    """
    assert declared(vocabulary) == {
        ("condition", "card_counters", "counter"): THE_USUAL_COUNTER,
        ("condition", "player_counters", "counter"): THE_USUAL_COUNTER,
        ("condition", "dice_equals", "value"): 0,
        ("condition", "dice_not_equals", "value"): 0,
        ("condition", "dice_greater", "value"): 0,
        ("condition", "dice_less", "value"): 0,
        ("target", "target_character", "count"): ONE,
        ("target", "target_curse", "count"): ONE,
        ("target", "target_deck_card", "count"): ONE,
        ("target", "target_loot", "count"): ONE,
        ("target", "target_monster", "count"): ONE,
        ("target", "target_player", "count"): ONE,
        ("target", "target_player_or_monster", "count"): ONE,
        ("target", "target_shop_item", "count"): ONE,
        ("target", "target_soul", "count"): ONE,
        ("target", "target_stack_item", "count"): ONE,
        ("target", "target_treasure", "count"): ONE,
        ("target", "deck_top", "count"): ONE,
        ("target", "deck_top", "deck"): THE_USUAL_DECK,
        ("target", "target_deck_card", "deck"): THE_USUAL_DECK,
        ("target", "target_deck_card", "pile"): THE_DECK_ITSELF,
    }


def test_a_declared_default_is_one_the_parameter_could_hold(
    vocabulary: Vocabulary,
) -> None:
    """
    A default outside the parameter's own domain would be a declaration that
    contradicts the one beside it.
    """
    for (family, owner, name), value in declared(vocabulary).items():
        table = (
            vocabulary.condition_shapes
            if family == "condition"
            else vocabulary.target_shapes
        )
        parameter = table[owner].params[name]

        if parameter.values:
            assert value in parameter.values, f"{owner}.{name}"

        if parameter.least is not None:
            assert value >= parameter.least, f"{owner}.{name}"


def test_the_counter_a_card_means_is_the_one_a_price_means() -> None:
    """
    `fsme.rules.costs` says the same word about a price paid in counters. The
    import cannot go the other way round, so the two are pinned here.
    """
    assert THE_USUAL_COUNTER == CHARGE


# --------------------------------------------- leaving it out and writing it


def a_context(**fields: Any) -> AbilityContext:
    """
    An ability part-way through running, with only what a condition reads.
    """
    return AbilityContext(**fields)


def carrying(counters: dict[str, int]) -> Any:
    """
    A card with counters on it, as `context.source`.
    """
    return SimpleNamespace(counters=dict(counters))


def test_a_counter_nobody_names_is_the_one_the_metadata_says(
    vocabulary: Vocabulary,
) -> None:
    """
    Run it both ways: with the counter left out, and with it written as
    whatever the shape declares. Neither branch names 'charge' — that is the
    point, because the test survives the word changing.
    """
    evaluator = ConditionEvaluator()
    state = make_state(players=2)
    said = vocabulary.condition_shapes["card_counters"].params["counter"].default

    # The rule: counters, unqualified, are charge counters — the same word a
    # price paid in counters means, which the test above pins.
    assert said == "charge"

    for held, expected in (({said: 1}, True), ({"egg": 1}, False)):
        context = a_context(source=carrying(held), controller=0)
        blank = {"card_counters": {"operator": ">=", "value": 1}}
        spelt = {"card_counters": {"operator": ">=", "value": 1, "counter": said}}

        assert evaluator.evaluate(blank, state, context) is expected
        assert evaluator.evaluate(spelt, state, context) is expected


def test_another_counter_is_not_replaced_by_the_default(
    vocabulary: Vocabulary,
) -> None:
    """
    A written answer wins. The declaration says what a blank means and nothing
    else, so a card naming its own counter goes on naming it.
    """
    evaluator = ConditionEvaluator()
    state = make_state(players=2)
    context = a_context(source=carrying({"egg": 3}), controller=0)
    asked = {"operator": ">=", "value": 1}

    assert evaluator.evaluate({"card_counters": asked}, state, context) is False
    assert (
        evaluator.evaluate(
            {"card_counters": asked | {"counter": "egg"}}, state, context
        )
        is True
    )


def test_a_die_nobody_compares_against_is_compared_against_the_default(
    vocabulary: Vocabulary,
) -> None:
    """
    Both ways again, for each of the four faces and several rolls. The number
    comes out of the shape, so this measures the join rather than restating it.
    """
    evaluator = ConditionEvaluator()
    state = make_state(players=2)

    for name in ("dice_equals", "dice_not_equals", "dice_greater", "dice_less"):
        said = vocabulary.condition_shapes[name].params["value"].default

        # The rule: a face nobody named is nought, which is a roll no die
        # shows — so "rolled a 6" written without the 6 is false, not true.
        assert said == 0, name

        for rolled in (0, 1, 6):
            context = a_context(controller=0, variables={"dice": rolled})

            assert evaluator.evaluate({name: {}}, state, context) == evaluator.evaluate(
                {name: {"value": said}}, state, context
            ), f"{name} rolled {rolled}"


def test_a_written_number_is_not_replaced_by_the_default() -> None:
    evaluator = ConditionEvaluator()
    state = make_state(players=2)
    context = a_context(controller=0, variables={"dice": 6})

    assert evaluator.evaluate({"dice_equals": {"value": 6}}, state, context) is True
    assert evaluator.evaluate({"dice_equals": {"value": 1}}, state, context) is False


def test_how_many_a_target_asks_for_when_it_does_not_say(
    vocabulary: Vocabulary,
) -> None:
    """
    `_ask` stops the game and says how few and how many may be picked. Leaving
    the count out and writing the declared count must stop it the same way.
    """
    resolver = TargetResolver()
    said = vocabulary.target_shapes["target_player"].params["count"].default

    def asked(written: dict[str, Any]) -> tuple[int, int]:
        state = make_state(players=3)
        context = a_context(controller=0)

        try:
            resolver.resolve(
                {"target_player": written}, state, context, RNG(state.seed)
            )
        except DecisionRequired as stop:
            return stop.minimum, stop.maximum

        raise AssertionError("expected the game to stop and ask")

    assert asked({}) == asked({"count": said})
    assert asked({"count": said + 1}) != asked({})
    # And the rule itself, not just the join: "choose a player" is one player.
    # The declaration and the line that applies it read one constant, so they
    # cannot drift from each other — only from the game, which is what this
    # sentence is for.
    assert asked({}) == (1, 1)


def test_which_deck_a_search_means_when_it_does_not_say(
    vocabulary: Vocabulary,
) -> None:
    """
    The two together name the zone the handler looks the card up in, so the
    pair has to spell a zone the state actually has.
    """
    shape = vocabulary.target_shapes["target_deck_card"]
    deck = shape.params["deck"].default
    pile = shape.params["pile"].default

    assert hasattr(make_state(players=2), f"{deck}_{pile}")
    # The rule, for the same reason as the count above: a search that names no
    # deck searches the loot deck, and searches it rather than its discards.
    assert f"{deck}_{pile}" == "loot_deck"


# ----------------------------------------------------------------- the form


def test_the_form_is_told_what_a_blank_box_means(can: dict[str, Any]) -> None:
    """
    The whole point of the stage: `otherwise` is what the page prints under an
    empty box, and it was `null` — drawn as "leave it out" — everywhere here.
    """
    seen = {
        (one["id"], field["id"]): field["otherwise"]
        for family in ("conditions", "targets")
        for one in can[family]
        for field in one["fields"]
    }

    assert seen[("target_player", "count")] == ONE
    assert seen[("target_deck_card", "deck")] == THE_USUAL_DECK
    assert seen[("target_deck_card", "pile")] == THE_DECK_ITSELF
    assert seen[("card_counters", "counter")] == THE_USUAL_COUNTER
    assert seen[("dice_equals", "value")] == 0


def test_declaring_a_default_asks_no_new_question(
    vocabulary: Vocabulary, can: dict[str, Any]
) -> None:
    """
    A default says what a blank means. It must not make the question required,
    change what kind of control draws it, or turn a free answer into a choice.
    """
    for (family, owner, name) in declared(vocabulary):
        table = (
            vocabulary.condition_shapes
            if family == "condition"
            else vocabulary.target_shapes
        )
        parameter = table[owner].params[name]

        assert not parameter.required, f"{owner}.{name}"
        assert parameter.role in ("amount", "which", "names"), f"{owner}.{name}"


# ---------------------------------------------- what is deliberately not said


AMBIGUOUS = (
    # `_has` reads `>=` and a number defaulting to one when no operator is
    # written, and `_compare` reads `==` and a number defaulting to nought when
    # one is; `nth_time_this_turn` reads `== 1` when the card wrote nothing at
    # all. One `operator` shape is shared by all twelve, so a single declared
    # value would be wrong for some of them.
    ("condition", "player_has_coins", "operator"),
    ("condition", "player_has_coins", "value"),
    ("condition", "player_has_coins", "amount"),
    ("condition", "nth_time_this_turn", "value"),
    ("condition", "player_hp", "value"),
    # What the event carried, which is not a number and has no default.
    ("condition", "event_value", "value"),
    # Whichever seat the ability's controller is — not a value at all.
    ("condition", "player_counters", "player"),
    # Whatever `count` turned out to be, which is an answer and not a literal.
    ("target", "target_player", "minimum"),
    ("target", "target_player", "maximum"),
)


def test_the_ambiguous_ones_are_still_undeclared(vocabulary: Vocabulary) -> None:
    """
    Each of these was measured and left alone on purpose: the engine reads them
    differently depending on what else the card wrote, and picking one value
    would be deciding a question rather than recording an answer.
    """
    for family, owner, name in AMBIGUOUS:
        table = (
            vocabulary.condition_shapes
            if family == "condition"
            else vocabulary.target_shapes
        )
        assert table[owner].params[name].default is None, f"{owner}.{name}"
