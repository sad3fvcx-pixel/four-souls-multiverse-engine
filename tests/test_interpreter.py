"""
The interpreter decides what will run, and runs nothing.
"""

from __future__ import annotations

import pytest
from conftest import make_state

from fsme.effects import UnknownEffectError, builtin_registry
from fsme.rng.rng import RNG
from fsme.runtime import (
    AbilityContext,
    ConditionEvaluator,
    Interpreter,
    InterpreterError,
    TargetResolver,
)


def build(nodes, *, state=None, context=None, seed=1):
    game_state = state if state is not None else make_state()
    ability_context = context if context is not None else AbilityContext(controller=0)

    interpreter = Interpreter(
        ConditionEvaluator(), TargetResolver(), builtin_registry()
    )

    return interpreter.build(nodes, game_state, ability_context, RNG(seed))


def test_shorthand_maps_to_the_declared_parameter() -> None:
    """
    ``{"gain_coins": 3}`` means amount, ``{"draw_loot": 3}`` means count.
    The effect declares which; the interpreter never guesses.
    """
    ops = build([{"gain_coins": 3}, {"draw_loot": 3}])

    assert ops[0].name == "gain_coins"
    assert ops[0].params == {"amount": 3}

    assert ops[1].name == "draw_loot"
    assert ops[1].params == {"count": 3}


def test_explicit_form_keeps_all_parameters() -> None:
    ops = build(
        [{"effect": "deal_damage", "amount": 2, "target": "current_monster"}]
    )

    assert ops[0].name == "deal_damage"
    assert ops[0].params == {"amount": 2}
    assert ops[0].target == "current_monster"


def test_shorthand_accepts_a_sibling_target() -> None:
    ops = build([{"gain_coins": 1, "target": "all_players"}])

    assert ops[0].target == "all_players"


def test_branch_is_resolved_before_execution() -> None:
    context = AbilityContext(controller=0)
    context.store("dice", 6)

    ops = build(
        [
            {
                "if": [{"dice_greater": 3}],
                "then": [{"gain_coins": 2}],
                "else": [{"gain_coins": 1}],
            }
        ],
        context=context,
    )

    assert len(ops) == 1
    assert ops[0].params == {"amount": 2}


def test_branch_takes_the_else_side() -> None:
    context = AbilityContext(controller=0)
    context.store("dice", 1)

    ops = build(
        [
            {
                "if": [{"dice_greater": 3}],
                "then": [{"gain_coins": 2}],
                "else": [{"gain_coins": 1}],
            }
        ],
        context=context,
    )

    assert ops[0].params == {"amount": 1}


def test_repeat_unrolls_the_queue() -> None:
    ops = build([{"repeat": 3, "effects": [{"gain_coins": 1}]}])

    assert len(ops) == 3
    assert all(op.name == "gain_coins" for op in ops)


def test_stop_truncates_the_remaining_operations() -> None:
    ops = build([{"gain_coins": 1}, "stop", {"gain_coins": 99}])

    assert len(ops) == 1


def test_stop_inside_a_branch_ends_the_ability() -> None:
    context = AbilityContext(controller=0)
    context.store("dice", 6)

    ops = build(
        [
            {"if": [{"dice_greater": 3}], "then": ["stop"]},
            {"gain_coins": 99},
        ],
        context=context,
    )

    assert ops == []


def test_for_each_binds_one_target_per_iteration() -> None:
    state = make_state(players=3)
    context = AbilityContext(controller=0)

    ops = build(
        [{"for_each": "opponents", "effects": [{"deal_damage": 1}]}],
        state=state,
        context=context,
    )

    assert len(ops) == 2

    bound = [context.targets[op.target] for op in ops]

    assert [player[0].player_id for player in bound] == [1, 2]


def test_unknown_effect_is_rejected() -> None:
    with pytest.raises(UnknownEffectError):
        build([{"summon_dragon": 1}])


def test_ambiguous_node_is_rejected() -> None:
    with pytest.raises(InterpreterError):
        build([{"gain_coins": 1, "draw_loot": 1}])


def test_runaway_nesting_is_stopped() -> None:
    node: dict = {"repeat": 1, "effects": [{"gain_coins": 1}]}

    for _ in range(20):
        node = {"repeat": 1, "effects": [node]}

    with pytest.raises(InterpreterError):
        build([node])
