"""
The interpreter decides what will run, and runs nothing.

Control flow opens as the queue is consumed, not when it is built, so a branch
can ask about what the effects before it did.
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


def interpreter() -> Interpreter:
    return Interpreter(ConditionEvaluator(), TargetResolver(), builtin_registry())


def plan(nodes, *, state=None, context=None, seed=1):
    """
    Expand a queue completely, the way the Runtime would if every effect were
    a no-op. Useful for inspecting structure; it executes nothing.
    """
    game_state = state if state is not None else make_state()
    ability_context = context if context is not None else AbilityContext(controller=0)

    engine = interpreter()
    rng = RNG(seed)

    ops = engine.build(nodes)
    index = 0

    while index < len(ops):
        op = ops[index]

        if not engine.is_control(op):
            index += 1
            continue

        expansion, stopped = engine.expand(op, game_state, ability_context, rng)

        if stopped:
            ops[index:] = expansion
        else:
            ops[index : index + 1] = expansion

    return ops


def test_shorthand_maps_to_the_declared_parameter() -> None:
    """
    ``{"gain_coins": 3}`` means amount, ``{"draw_loot": 3}`` means count.
    The effect declares which; the interpreter never guesses.
    """
    ops = plan([{"gain_coins": 3}, {"draw_loot": 3}])

    assert ops[0].name == "gain_coins"
    assert ops[0].params == {"amount": 3}

    assert ops[1].name == "draw_loot"
    assert ops[1].params == {"count": 3}


def test_explicit_form_keeps_all_parameters() -> None:
    ops = plan([{"effect": "deal_damage", "amount": 2, "target": "current_monster"}])

    assert ops[0].name == "deal_damage"
    assert ops[0].params == {"amount": 2}
    assert ops[0].target == "current_monster"


def test_shorthand_accepts_a_sibling_target() -> None:
    ops = plan([{"gain_coins": 1, "target": "all_players"}])

    assert ops[0].target == "all_players"


def test_a_branch_stays_in_the_queue_until_it_is_reached() -> None:
    """
    The bug this guards against: a branch decided when the queue was built
    could never see a die that had not been rolled yet.
    """
    ops = interpreter().build(
        [
            {"roll_dice": 6},
            {"if": [{"dice_equals": 6}], "then": [{"gain_coins": 2}]},
        ]
    )

    assert [op.name for op in ops] == ["roll_dice", "if"]
    assert interpreter().is_control(ops[1])


def test_a_branch_opens_on_the_condition_that_holds_then() -> None:
    context = AbilityContext(controller=0)
    context.store("dice", 6)

    ops = plan(
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


def test_a_branch_takes_the_else_side() -> None:
    context = AbilityContext(controller=0)
    context.store("dice", 1)

    ops = plan(
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
    ops = plan([{"repeat": 3, "effects": [{"gain_coins": 1}]}])

    assert len(ops) == 3
    assert all(op.name == "gain_coins" for op in ops)


def test_stop_truncates_the_remaining_operations() -> None:
    ops = plan([{"gain_coins": 1}, "stop", {"gain_coins": 99}])

    assert len(ops) == 1


def test_stop_inside_a_branch_ends_the_ability() -> None:
    context = AbilityContext(controller=0)
    context.store("dice", 6)

    ops = plan(
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

    ops = plan(
        [{"for_each": "opponents", "effects": [{"deal_damage": 1}]}],
        state=state,
        context=context,
    )

    assert len(ops) == 2

    bound = [context.targets[op.target] for op in ops]

    assert [player[0].player_id for player in bound] == [1, 2]


def test_unknown_effect_is_rejected() -> None:
    with pytest.raises(UnknownEffectError):
        plan([{"summon_dragon": 1}])


def test_ambiguous_node_is_rejected() -> None:
    with pytest.raises(InterpreterError):
        plan([{"gain_coins": 1, "draw_loot": 1}])


def test_a_runaway_loop_is_stopped() -> None:
    with pytest.raises(InterpreterError):
        plan([{"repeat": 10_000, "effects": [{"gain_coins": 1}]}])


def test_a_mixed_control_node_is_rejected() -> None:
    with pytest.raises(InterpreterError):
        interpreter().build([{"if": [], "repeat": 2}])
