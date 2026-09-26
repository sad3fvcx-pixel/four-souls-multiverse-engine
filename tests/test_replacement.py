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
from fsme.rules import STARTING_COINS
from fsme.runtime import StabilityError
from fsme.runtime.ability_context import AbilityContext
from fsme.runtime.errors import AbilityResolutionError, InterpreterError


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


def setup(*, players=2, interactive_priority=False):
    runtime, state = make_game(
        players=players, interactive_priority=interactive_priority
    )
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    return runtime, state


def give(state, player_id, definition, instance_id):
    card = make_instance(
        definition, controller=player_id, owner=player_id, instance_id=instance_id
    )
    state.player(player_id).treasures.add_top(card)

    return card


def pass_around(runtime, state, limit=40):
    """
    Let every window close, so the stack resolves in an interactive game.
    """
    for _ in range(limit):
        if not runtime.awaiting_priority:
            return

        runtime.submit(
            Command(type=CommandType.PASS_PRIORITY, player=state.priority.holder or 0)
        )


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
    assert state.player(1).pennies == STARTING_COINS + 1


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


def test_a_replacement_rolls_its_die_on_the_spot() -> None:
    """
    A replacement gets no window, so its roll cannot wait for one.

    The table answers a roll by responding to it, and there is nothing to
    respond to yet: the event being replaced has not happened. A death is
    offered for replacement by the State-Based Actions, which are not an
    ability and cannot be parked — so a replacement that rolled there used to
    throw the roll straight out of the engine, past the command that caused it.
    """
    runtime, state = setup(interactive_priority=True)

    lucky = make_definition(
        "test.lucky",
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger="before_death",
                effects=({"effect": "roll_dice", "sides": 6}, "cancel_event"),
                replacement=True,
                scope="any",
            ),
        ),
    )

    give(state, 1, lucky, "instance:lucky")

    runtime.context.apply("kill", [state.player(1)])
    runtime.run()

    assert state.player(1).alive is True, "the death was replaced"
    assert state.pending_roll is None, "no roll was left open"


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


# ----------------------------------------------------------------------
# A replacement that will not finish
# ----------------------------------------------------------------------
#
# `MAX_REPLACEMENT_DEPTH` above stops replacements *causing* one another for
# ever. What it cannot see is one replacement whose own effects grow without
# end, because that is a single replacement and never recurses.
#
# The interpreter bounds what one expansion may produce, and a loop inside a
# loop is not one expansion: the inner loop is a single operation while the
# outer one is being opened, and grows only when the queue reaches it. So
# `n` levels of `repeat` multiply past every guard the interpreter has —
# measured before this was written, six levels of eight ran a quarter of a
# million operations from two hundred bytes of card.
#
# `_resolve_ability` has always counted the turns of its own loop for exactly
# this reason. `_run_replacement_ops` is the same loop and did not.


def looping(card_id, effects, *, trigger="before_damage"):
    """
    A replacement whose body is whatever shape is being measured.
    """
    return make_definition(
        card_id,
        card_type=CardType.TREASURE,
        abilities=(
            Ability(
                trigger=trigger,
                effects=tuple(effects),
                replacement=True,
                scope="any",
            ),
        ),
    )


def nested(depth, times, leaf=None):
    """
    A loop of loops. The leaf gains a cent rather than preventing damage: run
    on its own, past no event, `prevent_damage` refuses before the count is
    anywhere near the limit, and the shape being measured is the loop.
    """
    node = leaf if leaf is not None else {"gain_coins": 1}

    for _ in range(depth):
        node = {"repeat": times, "effects": [node]}

    return node


def run_with(effects):
    """
    Put one replacement in play and let an ordinary blow meet it.

    The blow is dealt by an effect, so a replacement that stops itself stops
    inside one — and the executor wraps what it catches there, naming the
    effect it was running. The reason survives that, which is what the tests
    below read; `stopped_by` reaches the same guard with nothing wrapped
    around it.
    """
    runtime, state = setup()

    give(state, 0, striker(amount=1), "instance:striker")
    give(state, 1, looping("test.loop", effects), "instance:loop")

    activate(runtime)

    return state


def stopped_by(effects, *, players=2):
    """
    The same shape, run where nothing is wrapped around the guard.
    """
    runtime, state = setup(players=players)
    ability = looping("test.loop", effects).abilities[0]

    with pytest.raises(InterpreterError) as refused:
        runtime._run_replacement_ops(ability, AbilityContext(controller=0))

    return str(refused.value), runtime._interpreter.max_ops


def test_a_replacement_that_nests_loops_is_stopped() -> None:
    """
    The shape the interpreter's own guards cannot see.
    """
    said, limit = stopped_by([nested(6, 8)])

    assert said == f"replacement ran more than {limit} steps"


def test_replacement_loops_side_by_side_are_stopped_too() -> None:
    """
    Not only nesting. Each of these is small enough for every guard the
    interpreter has, and the queue they share is not.
    """
    said, _ = stopped_by([{"repeat": 200, "effects": [{"gain_coins": 1}]}] * 8)

    assert "replacement ran more than" in said


def test_a_replacement_that_nests_for_each_is_stopped() -> None:
    """
    `repeat` is not special: anything that opens into more than it was
    multiplies the same way.
    """
    node: dict = {"gain_coins": 1}

    for _ in range(6):
        node = {"for_each": "all_players", "effects": [node]}

    # Four players rather than two, because this one multiplies by however
    # many the loop finds and two of them do not reach the limit in six.
    said, _ = stopped_by([node], players=4)

    assert "replacement ran more than" in said


def test_the_count_is_of_turns_taken_and_not_of_effects_run() -> None:
    """
    The one that says what is being counted.

    Every leaf here is a loop of no times, so this shape runs *nothing* — and
    it still opens tens of thousands of control nodes on the way to running
    nothing. A limit counting effects would let it through; this one does not,
    because opening a node costs a turn whether or not anything comes of it.
    """
    said, _ = stopped_by(
        [nested(6, 8, leaf={"repeat": 0, "effects": [{"gain_coins": 1}]})]
    )

    assert "replacement ran more than" in said


def test_the_reason_survives_being_raised_inside_an_effect() -> None:
    """
    Damage is dealt by an effect, so this is how a player meets it.
    """
    with pytest.raises(AbilityResolutionError) as refused:
        run_with([nested(6, 8, leaf={"prevent_damage": 1})])

    assert "replacement ran more than" in str(refused.value)


def test_an_ordinary_replacement_still_replaces() -> None:
    """
    The other half, and the one that would catch a limit set too low. Three
    turns of the loop where the corpus never needs more than five.
    """
    state = run_with([{"repeat": 3, "effects": [{"prevent_damage": 1}]}])

    assert state.player(1).hp == 2


def test_the_two_loops_say_which_of_them_stopped() -> None:
    """
    Two loops count their own turns, and an error that did not say which had
    stopped would send somebody to the wrong one.
    """
    said, _ = stopped_by([nested(6, 8)])

    assert said.startswith("replacement ran")
    assert "ability ran" not in said


def test_the_limit_is_the_one_the_interpreter_already_had() -> None:
    """
    Read from the engine rather than written down again here.
    """
    from fsme.runtime.interpreter import DEFAULT_MAX_OPS

    runtime, _ = setup()

    assert runtime._interpreter.max_ops == DEFAULT_MAX_OPS


def test_the_replacement_vocabulary_is_registered() -> None:
    names = builtin_registry().names()

    for expected in ("prevent_damage", "cancel_event", "modify_event"):
        assert expected in names
