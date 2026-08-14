"""
Priority windows.

STACK.md section 9: after every push players get a chance to respond, and the
top object resolves only when everyone has passed consecutively.
"""

from __future__ import annotations

from conftest import make_game, make_instance, treasure_definition

from fsme.commands import Command, CommandType
from fsme.state import GamePhase


def start(runtime):
    """
    Start the game and let the opening loot step resolve.

    COMPREHENSIVE_RULES.md §3.1 opens a turn by putting a loot into the queue,
    so an interactive game begins with a window already open. A test about
    windows wants to open its own.
    """
    result = runtime.submit(Command(type=CommandType.START_GAME, player=0))

    while runtime.awaiting_priority:
        pass_priority(runtime, runtime.state.priority.holder or 0)

    return result


def pass_priority(runtime, player):
    return runtime.submit(Command(type=CommandType.PASS_PRIORITY, player=player))


def give_treasure(state, player_id, card_id="test.item", effects=({"gain_coins": 3},)):
    card = make_instance(
        treasure_definition(card_id, effects=effects),
        controller=player_id,
        owner=player_id,
        instance_id=f"instance:{card_id}",
    )
    state.player(player_id).treasures.add_top(card)

    return card


def test_no_window_opens_when_priority_is_not_interactive() -> None:
    """
    Headless games treat everyone as having passed, which is what lets tests
    and simulations run without an input source.
    """
    runtime, state = make_game()
    start(runtime)
    give_treasure(state, 0)

    runtime.submit(
        Command(type=CommandType.ACTIVATE_TREASURE, player=0, payload={"index": 0})
    )

    assert runtime.awaiting_priority is False
    assert state.player(0).pennies == 3
    assert runtime.is_stable()


def test_an_ability_waits_for_everyone_to_pass() -> None:
    runtime, state = make_game(interactive_priority=True)
    start(runtime)
    give_treasure(state, 0)

    runtime.submit(
        Command(type=CommandType.ACTIVATE_TREASURE, player=0, payload={"index": 0})
    )

    assert runtime.awaiting_priority is True
    assert not state.stack.is_empty()
    assert state.player(0).pennies == 0

    assert pass_priority(runtime, 0).accepted
    assert runtime.awaiting_priority is True

    assert pass_priority(runtime, 1).accepted

    assert state.player(0).pennies == 3
    assert state.stack.is_empty()
    assert runtime.awaiting_priority is False


def test_priority_starts_with_the_active_player_and_moves_in_seat_order() -> None:
    runtime, state = make_game(players=3, interactive_priority=True)
    start(runtime)
    give_treasure(state, 0)

    runtime.submit(
        Command(type=CommandType.ACTIVATE_TREASURE, player=0, payload={"index": 0})
    )

    assert state.priority.holder == 0

    pass_priority(runtime, 0)
    assert state.priority.holder == 1

    pass_priority(runtime, 1)
    assert state.priority.holder == 2


def test_only_the_holder_may_pass() -> None:
    runtime, state = make_game(interactive_priority=True)
    start(runtime)
    give_treasure(state, 0)

    runtime.submit(
        Command(type=CommandType.ACTIVATE_TREASURE, player=0, payload={"index": 0})
    )

    result = pass_priority(runtime, 1)

    assert result.rejected
    assert "holds priority" in result.reason


def test_a_response_reopens_the_window() -> None:
    """
    Players who already passed must get to answer the new object too.
    """
    runtime, state = make_game(interactive_priority=True)
    start(runtime)

    first = give_treasure(state, 0, "test.first", ({"gain_coins": 1},))
    give_treasure(state, 1, "test.second", ({"gain_coins": 5},))

    runtime.submit(
        Command(type=CommandType.ACTIVATE_TREASURE, player=0, payload={"index": 0})
    )

    pass_priority(runtime, 0)
    assert state.priority.holder == 1

    # Player 1 responds instead of passing.
    runtime.submit(
        Command(type=CommandType.ACTIVATE_TREASURE, player=1, payload={"index": 0})
    )

    assert len(state.stack) == 2
    assert state.priority.passes == 0
    assert state.priority.holder == 0

    pass_priority(runtime, 0)
    pass_priority(runtime, 1)

    # The response resolved first, the original ability is still waiting.
    assert state.player(1).pennies == 5
    assert state.player(0).pennies == 0
    assert len(state.stack) == 1

    pass_priority(runtime, 0)
    pass_priority(runtime, 1)

    assert state.player(0).pennies == 1
    assert state.stack.is_empty()
    assert first.tapped is True


def test_non_response_commands_are_refused_during_a_window() -> None:
    runtime, state = make_game(interactive_priority=True)
    start(runtime)
    give_treasure(state, 0)

    runtime.submit(
        Command(type=CommandType.ACTIVATE_TREASURE, player=0, payload={"index": 0})
    )

    result = runtime.submit(Command(type=CommandType.END_TURN, player=0))

    assert result.rejected
    assert "not a response" in result.reason


def test_passing_without_a_window_is_refused() -> None:
    runtime, state = make_game(interactive_priority=True)
    start(runtime)

    result = pass_priority(runtime, 0)

    assert result.rejected
    assert "no priority window" in result.reason


def test_combat_rounds_are_interruptible_under_priority() -> None:
    runtime, state = make_game(interactive_priority=True)
    start(runtime)

    runtime.submit(Command(type=CommandType.END_PHASE, player=0))

    assert state.turn.phase is GamePhase.ACTION

    runtime.submit(
        Command(type=CommandType.ATTACK, player=0, payload={"index": 0})
    )

    assert runtime.awaiting_priority is True
    assert state.combat.active is True
    assert state.combat.round_number == 0
