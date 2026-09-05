"""
Checking what a card asks before it asks it.

An effect says what it takes in its own signature, so the engine could be read
for it. A condition cannot: all forty-one have the same three arguments and a
bag of parameters, so nothing about `{"player_hp": {"operator": "<"}}` can be
learned by looking at `_player_hp`.

What can be read is which helper a condition hands its parameters to, and the
helper is where they are understood. `_compare` is the only code that knows an
operator is one of six; eight conditions call it. So the parameters are
described once per helper, next to the helper, and each condition names the set
it inherits on the line it is already registered on. There is no second table
to keep in step with the first.

The mistake this exists for is quiet. A condition drops a parameter it does not
recognise, so `{"operatr": "<", "value": 2}` is not a card that fails — it is a
card that silently means "equal to zero" and plays a whole game that way.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards import validate_card
from fsme.content import ContentLoader, Vocabulary
from fsme.content.errors import InvalidContentError
from fsme.runtime.condition_evaluator import ConditionEvaluator
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

EXPANSION = "example_expansion"


@pytest.fixture(scope="module")
def vocabulary() -> Vocabulary:
    return engine_vocabulary()


def a_card(
    *conditions: Any,
    statics: Any = None,
    effects: Any = None,
    card_id: str = "example_expansion-loot-dark_coin",
) -> dict:
    card: dict[str, Any] = {
        "id": card_id,
        "name": "Dark Coin",
        "type": "loot",
        "expansion": EXPANSION,
        "schema_version": "1",
        "abilities": [
            {
                "trigger": "on_play",
                "conditions": list(conditions),
                "effects": effects
                if effects is not None
                else [{"effect": "gain_coins", "amount": 1}],
            }
        ],
    }

    if statics is not None:
        card["statics"] = statics

    return card


def complaints(vocabulary: Vocabulary, card: dict) -> list[str]:
    return validate_card(
        card,
        known_effects=vocabulary.effects,
        known_triggers=vocabulary.triggers,
        known_conditions=vocabulary.conditions,
        known_targets=vocabulary.targets,
        shapes=vocabulary.shapes,
        condition_shapes=vocabulary.condition_shapes,
    )


def asking(vocabulary: Vocabulary, *conditions: Any) -> list[str]:
    return complaints(vocabulary, a_card(*conditions))


def a_set(tmp_path: Path, *cards: dict) -> Path:
    """
    A one-set content tree, built where a test may write.
    """
    root = tmp_path / "root"
    (root / EXPANSION / "cards").mkdir(parents=True)

    (root / EXPANSION / "manifest.json").write_text(
        json.dumps(
            {
                "id": EXPANSION,
                "name": "Example",
                "version": "1.0.0",
                "schema_version": "1",
            }
        ),
        encoding="utf-8",
    )
    (root / EXPANSION / "cards" / "loot.json").write_text(
        json.dumps({"cards": list(cards)}), encoding="utf-8"
    )

    return root


# ----------------------------------------------------------------------
# The description stays beside the implementation
# ----------------------------------------------------------------------


def test_every_condition_the_engine_ships_says_what_it_takes() -> None:
    """
    The point of describing conditions where they are registered is that one
    cannot be added without a description. If a new condition may arrive
    undescribed, the descriptions are a separate table again.
    """
    evaluator = ConditionEvaluator()
    shapes = evaluator.shapes()

    undescribed = sorted(
        name for name in evaluator.names() if shapes[name].open_ended
    )

    assert undescribed == []


def test_the_operators_come_from_the_table_that_performs_them(
    vocabulary: Vocabulary,
) -> None:
    """
    Not from a list written out a second time. A comparison the engine cannot
    make and a comparison validation refuses have to be the same set, or one
    of them is wrong.
    """
    from fsme.runtime.condition_evaluator import _COMPARISONS

    shape = vocabulary.condition_shape("player_hp")

    assert shape is not None
    assert set(shape.params["operator"].values) == set(_COMPARISONS)


def test_a_condition_registered_without_a_description_is_not_judged() -> None:
    """
    Saying nothing is not the same as accepting everything. Nobody outside a
    game may refuse a parameter of a condition whose author did not describe
    it — but nothing here treats that silence as permission either.
    """
    evaluator = ConditionEvaluator()
    evaluator.register("weather_is_nice", lambda state, context, params: True)

    shape = evaluator.shapes()["weather_is_nice"]

    assert shape.open_ended
    assert dict(shape.params) == {}


# ----------------------------------------------------------------------
# Good cards are left alone
# ----------------------------------------------------------------------


def test_the_forms_a_card_may_use_all_pass(vocabulary: Vocabulary) -> None:
    assert asking(vocabulary, "first_turn") == []
    assert asking(vocabulary, {"dice_equals": 6}) == []
    assert asking(vocabulary, {"player_hp": {"operator": "<", "value": 2}}) == []
    assert (
        asking(vocabulary, {"condition": "player_hp", "operator": "<", "value": 2})
        == []
    )
    assert asking(vocabulary, {"and": [{"dice_greater": 2}, {"dice_less": 5}]}) == []


def test_the_one_value_this_layer_cannot_judge_is_left_alone(
    vocabulary: Vocabulary,
) -> None:
    """
    `event_value` compares against whatever the event carries — a number, a
    flag or a name. A rule that made it a number would refuse a card asking a
    perfectly fair question.
    """
    assert asking(vocabulary, {"event_value": {"key": "hit", "value": False}}) == []
    assert (
        asking(vocabulary, {"event_value": {"key": "shield", "value": "host_hat"}})
        == []
    )
    assert asking(vocabulary, {"event_value": {"key": "hits", "value": 2}}) == []


# ----------------------------------------------------------------------
# Bad cards are refused
# ----------------------------------------------------------------------


def test_an_unknown_condition_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = asking(vocabulary, {"player_hpp": 3})

    assert "unknown condition 'player_hpp'" in message
    assert "player_hp" in message


def test_a_parameter_of_the_wrong_kind_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = asking(vocabulary, {"condition": "player_hp", "value": "many"})

    assert "wants a whole number for 'value'" in message
    assert "'many'" in message


def test_a_flag_is_not_a_number(vocabulary: Vocabulary) -> None:
    """
    `True` is an integer in Python and is not a number on a card.
    """
    (message,) = asking(vocabulary, {"dice_equals": True})

    assert "wants a whole number for 'value'" in message


def test_a_comparison_the_engine_cannot_make_is_refused(
    vocabulary: Vocabulary,
) -> None:
    (message,) = asking(vocabulary, {"player_hp": {"operator": "=<", "value": 2}})

    assert "'=<'" in message
    assert "'<='" in message


def test_a_parameter_the_condition_would_drop_is_refused(
    vocabulary: Vocabulary,
) -> None:
    """
    The quiet one. `operatr` is not read, so the comparison becomes the
    default and the card plays a game nobody asked for.
    """
    (message,) = asking(vocabulary, {"player_hp": {"operatr": "<", "value": 2}})

    assert "takes no 'operatr'" in message
    assert "did you mean 'operator'" in message


def test_a_number_outside_what_the_condition_can_mean_is_refused(
    vocabulary: Vocabulary,
) -> None:
    (period,) = asking(vocabulary, {"nth_time_this_turn": {"every": 0}})
    (seat,) = asking(vocabulary, {"player_alive": {"player": -1}})

    assert "at least 1" in period
    assert "at least 0" in seat


def test_a_condition_missing_what_it_needs_is_refused(
    vocabulary: Vocabulary,
) -> None:
    (message,) = asking(vocabulary, {"event_value": {"value": 3}})

    assert "'event_value' needs 'key'" in message


# ----------------------------------------------------------------------
# Everywhere a card may write a condition
# ----------------------------------------------------------------------


def test_a_condition_nested_in_a_boolean_is_checked(vocabulary: Vocabulary) -> None:
    (message,) = asking(
        vocabulary, {"and": [{"dice_greater": 2}, {"dice_lss": 5}]}
    )

    assert "unknown condition 'dice_lss'" in message
    assert ".and[1]" in message


def test_a_condition_on_a_static_is_checked(vocabulary: Vocabulary) -> None:
    """
    Statics were never checked at all. A passive modifier that only applies
    sometimes says when in exactly the same words an ability does.
    """
    card = a_card(
        statics=[
            {
                "stat": "attack",
                "amount": 1,
                "conditions": [{"player_hp": {"operator": "!!", "value": 1}}],
            }
        ]
    )

    (message,) = complaints(vocabulary, card)

    assert "statics[0].conditions[0]" in message
    assert "'!!'" in message


def test_a_condition_on_a_branch_inside_an_ability_is_checked(
    vocabulary: Vocabulary,
) -> None:
    """
    `{"if": [...], "then": [...]}` is the commonest place in the shipped cards
    for a condition to appear, and the least visible.
    """
    card = a_card(
        effects=[
            {
                "if": [{"dice_less": "three"}],
                "then": [{"effect": "gain_coins", "amount": 1}],
            }
        ]
    )

    (message,) = complaints(vocabulary, card)

    assert "effects[0].if[0]" in message
    assert "wants a whole number" in message


def test_every_problem_in_a_card_is_reported_at_once(
    vocabulary: Vocabulary,
) -> None:
    messages = asking(
        vocabulary,
        {"player_hpp": 1},
        {"player_hp": {"operator": "=<", "value": 2}},
        {"dice_equals": "six"},
    )

    assert len(messages) == 3


# ----------------------------------------------------------------------
# Through the loader, and against everything already written
# ----------------------------------------------------------------------


def test_the_loader_refuses_a_set_whose_condition_is_wrong(tmp_path: Path) -> None:
    root = a_set(
        tmp_path, a_card({"player_hp": {"operator": "=<", "value": 2}})
    )

    with pytest.raises(InvalidContentError) as raised:
        load_content(root)

    assert "'=<'" in str(raised.value)
    assert EXPANSION in str(raised.value)


def test_a_set_whose_conditions_are_right_loads_and_plays(tmp_path: Path) -> None:
    root = a_set(tmp_path, a_card({"player_hp": {"operator": "<=", "value": 2}}))

    library = load_content(root)

    assert library.registry().get("example_expansion-loot-dark_coin") is not None


def test_a_vocabulary_without_condition_shapes_checks_names_only(
    tmp_path: Path,
) -> None:
    """
    A caller who has no engine to ask still gets spelling checked. What they
    do not get is an opinion about parameters nobody described.
    """
    engine = engine_vocabulary()
    names_only = Vocabulary.of(
        effects=engine.effects,
        triggers=engine.triggers,
        conditions=engine.conditions,
        targets=engine.targets,
    )

    root = a_set(tmp_path, a_card({"player_hp": {"operator": "=<", "value": 2}}))

    library = ContentLoader(names_only).load_root(root)

    assert library.registry().get("example_expansion-loot-dark_coin") is not None


def test_everything_already_written_still_passes() -> None:
    """
    The test that matters. Every condition in `content/` was written by
    somebody who decided it was right; if a rule above is wrong, it shows here
    and nowhere else.
    """
    library = load_content(CONTENT_ROOT)

    assert len(library.registry()) > 1000
