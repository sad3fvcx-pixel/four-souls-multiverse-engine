"""
Replacement effects.

EVENT_SYSTEM.md section 7: a replacement changes an event before it resolves.
STACK.md section 12: it does not use the stack. That is what separates
preventing damage from reacting to it.
"""

from __future__ import annotations

import pytest
from conftest import make_definition, make_game, make_instance

from fsme.cards import Ability, CardType
from fsme.commands import Command, CommandType
from fsme.effects import EffectExecutionError, builtin_registry
from fsme.events import EventType
from fsme.runtime import StabilityError


def shield(card_id="test.shield", *, amount=1, conditions=(), trigger="before_damage"):
    return make_definition(
        card_id,
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger=trigger,
                conditions=tuple(conditions),
                effects=({"prevent_damage": amount},),
                replacement=True,
                scope="any",
            ),
        ),
    )


def striker(card_id="test.striker", *, amount=2, target="opponents"):
    return make_definition(
        card_id,
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="on_activate",
                effects=(
                    {"effect": "deal_damage", "amount": amount, "target": target},
                ),
            ),
        ),
    )


def setup(*, players=2):
    runtime, state = make_game(players=players)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    return runtime, state


def give(state, player_id, definition, instance_id):
    card = make_instance(
        definition, controller=player_id, owner=player_id, instance_id=instance_id
    )
    state.player(player_id).treasures.add_top(card)

    return card


def activate(runtime, player=0, index=0):
    return runtime.submit(
        Command(
            type=CommandType.ACTIVATE_TREASURE, player=player, payload={"index": index}
        )
    )


def test_a_replacement_reduces_damage_before_it_lands() -> None:
    runtime, state = setup()

    give(state, 0, striker(amount=2), "instance:striker")
    give(state, 1, shield(amount=1), "instance:shield")

    activate(runtime)

    assert state.player(1).hp == 1


def test_preventing_everything_cancels_the_event() -> None:
    """
    Nothing should be recorded as having dealt zero damage.
    """
    runtime, state = setup()

    give(state, 0, striker(amount=1), "instance:striker")
    give(state, 1, shield(amount=5), "instance:shield")

    activate(runtime)

    assert state.player(1).hp == 2
    assert EventType.DAMAGE_DEALT not in [event.type for event in runtime.history]


def test_a_replacement_never_reaches_the_stack() -> None:
    runtime, state = setup()

    give(state, 0, striker(amount=2), "instance:striker")
    give(state, 1, shield(amount=1), "instance:shield")

    pushes = [
        event
        for event in runtime.history
        if event.type is EventType.STACK_PUSH
    ]

    activate(runtime)

    after = [
        event
        for event in runtime.history
        if event.type is EventType.STACK_PUSH
    ]

    # Only the striker's own activated ability was ever stacked.
    assert len(after) - len(pushes) == 1


def test_each_replacement_applies_once_per_event() -> None:
    """
    Two cards that each reduce damage must not bounce the event between them.
    """
    runtime, state = setup()

    give(state, 0, striker(amount=3), "instance:striker")
    give(state, 1, shield("test.shield_a", amount=1), "instance:shield_a")
    give(state, 1, shield("test.shield_b", amount=1), "instance:shield_b")

    activate(runtime)

    assert state.player(1).hp == 1


def test_a_replacement_may_be_conditional() -> None:
    runtime, state = setup()

    give(state, 0, striker(amount=1), "instance:striker")
    give(
        state,
        1,
        shield(amount=1, conditions=({"player_has_coins": 5},)),
        "instance:shield",
    )

    activate(runtime)

    assert state.player(1).hp == 1

    state.player(1).heal(5)
    state.player(1).pennies = 5
    state.player(0).treasures.cards[0].tapped = False

    activate(runtime)

    assert state.player(1).hp == 2


def test_an_ordinary_trigger_still_sees_the_event() -> None:
    """
    A replacement edits the event; the event is then queued as usual, so
    triggered abilities react to what actually happened.
    """
    runtime, state = setup()

    give(state, 0, striker(amount=3), "instance:striker")
    give(state, 1, shield(amount=1), "instance:shield")

    reactor = make_definition(
        "test.reactor",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(trigger="damage_dealt", effects=({"gain_coins": 1},)),
        ),
    )
    give(state, 1, reactor, "instance:reactor")

    activate(runtime)

    assert state.player(1).hp == 0
    assert state.player(1).pennies == 1


def test_healing_can_be_replaced() -> None:
    runtime, state = setup()

    state.player(0).hp = 1

    healer = make_definition(
        "test.healer",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="on_activate",
                effects=({"effect": "heal", "amount": 1, "target": "controller"},),
            ),
        ),
    )
    blocker = make_definition(
        "test.blocker",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="before_heal",
                effects=("cancel_event",),
                replacement=True,
                scope="any",
            ),
        ),
    )

    give(state, 0, healer, "instance:healer")
    give(state, 1, blocker, "instance:blocker")

    activate(runtime)

    assert state.player(0).hp == 1


def test_modify_event_changes_a_carried_value() -> None:
    runtime, state = setup()

    give(state, 0, striker(amount=1), "instance:striker")

    amplifier = make_definition(
        "test.amplifier",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="before_damage",
                effects=({"effect": "modify_event", "key": "amount", "delta": 1},),
                replacement=True,
                scope="any",
            ),
        ),
    )
    give(state, 1, amplifier, "instance:amplifier")

    activate(runtime)

    assert state.player(1).hp == 0


def test_a_replacement_inside_a_replacement_gives_the_event_back() -> None:
    """
    A replacement may cause an event that is itself replaced.

    The inner replacement has its own event to edit; when it is done, the outer
    ability must still be editing the one it started on. Losing it would strand
    a half-applied replacement — the event edited by nobody, and the rest of
    the ability with nothing to work on.
    """
    runtime, state = setup()

    state.player(1).hp = 1

    healing_shield = make_definition(
        "test.healing_shield",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="before_damage",
                effects=(
                    {"effect": "heal", "amount": 1, "target": "controller"},
                    "cancel_event",
                ),
                replacement=True,
                scope="any",
            ),
        ),
    )
    blocker = make_definition(
        "test.blocker",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="before_heal",
                effects=("cancel_event",),
                replacement=True,
                scope="any",
            ),
        ),
    )

    give(state, 0, striker(amount=1), "instance:striker")
    give(state, 0, blocker, "instance:blocker")
    give(state, 1, healing_shield, "instance:healing_shield")

    activate(runtime)

    # The heal was cancelled by the inner replacement and the damage by the
    # outer one, which is only possible if the outer one still had its event.
    assert state.player(1).hp == 1


def test_replacement_effects_refuse_to_run_outside_a_window() -> None:
    runtime, state = setup()

    with pytest.raises(EffectExecutionError):
        runtime.context.apply("prevent_damage", [], amount=1)


def test_runaway_replacement_chains_are_stopped() -> None:
    """
    A replacement that causes the event it replaces is a content bug, and the
    engine reports it instead of hanging.
    """
    runtime, state = setup()

    loop = make_definition(
        "test.loop",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="before_damage",
                effects=(
                    {"effect": "deal_damage", "amount": 1, "target": "opponents"},
                ),
                replacement=True,
                scope="any",
            ),
        ),
    )

    give(state, 0, striker(amount=1), "instance:striker")
    give(state, 1, loop, "instance:loop")

    with pytest.raises(StabilityError):
        activate(runtime)


def test_the_replacement_vocabulary_is_registered() -> None:
    names = builtin_registry().names()

    for expected in ("prevent_damage", "cancel_event", "modify_event"):
        assert expected in names
