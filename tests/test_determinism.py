"""
Determinism: the same seed and the same input produce the same game.

ENGINE_SPEC.md calls determinism a mandatory property of the engine, so it is
tested as a property rather than as a feature of any one mechanic.
"""

from __future__ import annotations

from conftest import make_definition, make_instance, make_runtime, make_state

from fsme.cards import Ability, CardType
from fsme.events import EventType


def dice_card():
    return make_definition(
        "test.dice",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="on_activate",
                effects=(
                    {"roll_dice": 6},
                    {
                        "if": [{"dice_greater": 3}],
                        "then": [{"gain_coins": 2}],
                        "else": [{"gain_coins": 1}],
                    },
                ),
            ),
        ),
    )


def play(seed: int, activations: int = 8):
    state = make_state(seed=seed)
    card = make_instance(dice_card())
    state.player(0).treasures.add_top(card)

    runtime = make_runtime(state)

    rolls: list[int] = []
    runtime.subscribe(EventType.AFTER_ROLL, lambda event: rolls.append(event.get("value")))

    for _ in range(activations):
        runtime.dispatch(EventType.ON_ACTIVATE, source=card, controller=0)

    return runtime, state, rolls


def signature(runtime, state, rolls) -> tuple:
    return (
        tuple(rolls),
        state.player(0).pennies,
        state.ids.counter,
        tuple(
            (event.event_id, str(event.type), event.sequence)
            for event in runtime.history
        ),
    )


def test_same_seed_produces_an_identical_game() -> None:
    first = signature(*play(seed=1234))
    second = signature(*play(seed=1234))

    assert first == second


def test_different_seeds_diverge() -> None:
    first = signature(*play(seed=1))
    second = signature(*play(seed=99))

    assert first != second


def test_event_identifiers_are_reproducible() -> None:
    runtime_a, state_a, _ = play(seed=7, activations=3)
    runtime_b, state_b, _ = play(seed=7, activations=3)

    assert [event.event_id for event in runtime_a.history] == [
        event.event_id for event in runtime_b.history
    ]

    assert state_a.ids.counter == state_b.ids.counter


def test_shuffling_consumes_the_engine_rng_only() -> None:
    """
    Two states with the same seed shuffle the same way.
    """
    first = make_state(seed=42)
    second = make_state(seed=42)

    for state in (first, second):
        for index in range(10):
            state.loot_discard.add_top(f"card-{index}")

    runtime_a = make_runtime(first)
    runtime_b = make_runtime(second)

    runtime_a.effects.execute(
        "draw_loot", runtime_a.context, [first.player(0)], count=5
    )
    runtime_b.effects.execute(
        "draw_loot", runtime_b.context, [second.player(0)], count=5
    )

    assert first.player(0).hand.cards == second.player(0).hand.cards
