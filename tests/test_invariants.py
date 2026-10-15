"""
Engine invariants.

ENGINE_INVARIANTS.md says a violated invariant means a bug in the engine.
These tests assert the ones the current implementation is able to guarantee.
"""

from __future__ import annotations

import pytest
from conftest import make_definition, make_instance, make_runtime, make_state

from fsme.cards import Ability, CardType
from fsme.events import EventType
from fsme.rng.rng import RNG
from fsme.runtime import AbilityContext, ConditionEvaluator, TargetResolver


def snapshot(state) -> tuple:
    """
    Capture everything a condition could plausibly disturb.
    """
    return (
        [(player.hp, player.pennies, player.soul_count, player.alive) for player in state.players],
        len(state.stack),
        len(state.events),
        state.ids.counter,
        state.game_over,
    )


@pytest.mark.parametrize(
    "condition",
    [
        "player_alive",
        "player_active",
        {"player_has_coins": 1},
        {"player_hp": {"operator": ">", "value": 0}},
        "stack_empty",
        "first_turn",
        {"dice_greater": 3},
    ],
)
def test_conditions_never_change_the_game(condition) -> None:
    state = make_state()
    evaluator = ConditionEvaluator()

    context = AbilityContext(controller=0)
    context.store("dice", 4)

    before = snapshot(state)
    evaluator.evaluate(condition, state, context)

    assert snapshot(state) == before


def test_conditions_do_not_consume_randomness() -> None:
    """
    The RNG belongs to GameState, so a condition that rolled would be writing.
    """
    state = make_state()
    rng = RNG(state.seed)
    before = rng.get_state()

    ConditionEvaluator().evaluate("player_alive", state, AbilityContext(controller=0))

    assert rng.get_state() == before


def test_chance_is_not_available_as_a_condition() -> None:
    """
    CONDITION_REGISTRY.md lists it; the engine deliberately does not implement
    it, because rolling inside a condition would mutate the RNG state.
    """
    assert "chance" not in ConditionEvaluator().names()


@pytest.mark.parametrize(
    "target",
    ["all_players", "opponents", "controller", "active_player", "all_monsters"],
)
def test_non_random_targets_never_change_the_game(target) -> None:
    state = make_state(players=3)
    resolver = TargetResolver()

    before = snapshot(state)
    resolver.resolve(target, state, AbilityContext(controller=0), RNG(1))

    assert snapshot(state) == before


def test_stack_identifiers_are_unique() -> None:
    state = make_state()

    definition = make_definition(
        "test.item",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(trigger="turn_start", effects=({"gain_coins": 1},)),
        ),
    )

    for index, player in enumerate(state.players):
        player.treasures.add_top(
            make_instance(
                definition,
                controller=index,
                owner=index,
                instance_id=f"instance:{index}",
            )
        )

    runtime = make_runtime(state)

    seen: list[str] = []

    def record(event) -> None:
        seen.append(event.get("stack_id"))

    runtime.subscribe(EventType.STACK_PUSH, record)
    runtime.dispatch(EventType.TURN_START)

    assert len(seen) == 2
    assert len(set(seen)) == len(seen)


def test_every_event_is_recorded_in_order() -> None:
    """
    The replay log is reconstructed from this history, so it must be complete
    and monotonic.
    """
    state = make_state()

    card = make_instance(
        make_definition(
            "test.item",
            card_type=CardType.TREASURE,
            abilities=(
                Ability(trigger="on_activate", effects=({"gain_coins": 1},)),
            ),
        )
    )
    state.player(0).treasures.add_top(card)

    runtime = make_runtime(state)
    runtime.dispatch(EventType.ON_ACTIVATE, source=card, controller=0)

    sequences = [event.sequence for event in runtime.history]

    assert sequences == sorted(sequences)
    assert all(event.event_id for event in runtime.history)


def test_definitions_are_shared_and_unchanged_by_play() -> None:
    """
    A card definition is immutable, so playing with it cannot alter it.
    """
    definition = make_definition(
        "test.item",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(trigger="on_activate", effects=({"gain_coins": 1},)),
        ),
    )
    original = (definition.id, definition.name, definition.type, definition.abilities)

    state = make_state()
    card = make_instance(definition)
    state.player(0).treasures.add_top(card)

    runtime = make_runtime(state)
    runtime.dispatch(EventType.ON_ACTIVATE, source=card, controller=0)

    assert card.definition is definition
    assert (
        definition.id,
        definition.name,
        definition.type,
        definition.abilities,
    ) == original
