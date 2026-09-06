"""
The command system is the only way into the engine.
"""

from __future__ import annotations

from conftest import make_game, make_runtime, make_state

from fsme.commands import Command, CommandRegistry, CommandType
from fsme.events import EventType


def start(runtime):
    return runtime.submit(Command(type=CommandType.START_GAME, player=0))


def test_a_valid_command_is_accepted_and_produces_events() -> None:
    runtime, state = make_game()

    result = start(runtime)

    assert result.accepted
    assert result.command.command_id
    assert EventType.GAME_START in [event.type for event in result.events]
    assert state.started is True


def test_an_illegal_command_changes_nothing() -> None:
    """
    RULES_SPEC.md section 11: illegal commands never modify GameState.
    """
    runtime, state = make_game()
    start(runtime)

    before = (
        state.ids.counter,
        state.turn.turn_number,
        state.turn.active_player,
        [player.pennies for player in state.players],
        len(state.events),
    )

    result = runtime.submit(Command(type=CommandType.END_TURN, player=1))

    assert result.rejected
    assert "active player" in result.reason

    after = (
        state.ids.counter,
        state.turn.turn_number,
        state.turn.active_player,
        [player.pennies for player in state.players],
        len(state.events),
    )

    assert after == before


def test_a_rejected_command_gets_no_identifier() -> None:
    """
    Allocating an id would advance state a replay has to reproduce.
    """
    runtime, state = make_game()

    result = runtime.submit(Command(type=CommandType.END_TURN, player=0))

    assert result.rejected
    assert result.command.command_id == ""
    assert result.command.sequence == 0


def test_unknown_command_types_are_rejected_safely() -> None:
    """
    COMMAND_SYSTEM.md section 14: an expansion may add command types, and a
    type this engine has no handler for is refused rather than guessed at.
    """
    from fsme.rules import StartGameHandler

    partial = CommandRegistry()
    partial.register(CommandType.START_GAME, StartGameHandler())

    runtime = make_runtime(make_state(), commands=partial)

    result = runtime.submit(Command(type=CommandType.ATTACK, player=0))

    assert result.rejected
    assert "no handler registered" in result.reason


def test_commands_from_unknown_players_are_rejected() -> None:
    runtime, _ = make_game()

    result = runtime.submit(Command(type=CommandType.START_GAME, player=7))

    assert result.rejected
    assert "unknown player" in result.reason


def test_every_command_is_logged_with_its_outcome() -> None:
    runtime, _ = make_game()

    start(runtime)
    runtime.submit(Command(type=CommandType.END_TURN, player=1))

    log = runtime.command_log

    assert [entry.accepted for entry in log] == [True, False]
    assert [entry.command.type for entry in log] == [
        CommandType.START_GAME,
        CommandType.END_TURN,
    ]


def test_starting_twice_is_refused() -> None:
    runtime, _ = make_game()

    assert start(runtime).accepted
    assert start(runtime).rejected


def test_registry_refuses_a_second_handler_for_one_type() -> None:
    registry = CommandRegistry()

    class Handler:
        def validate(self, command, state):
            return None

        def execute(self, command, context):
            return None

    registry.register(CommandType.END_TURN, Handler())

    try:
        registry.register(CommandType.END_TURN, Handler())
    except Exception as error:  # noqa: BLE001 - the type is asserted below
        assert "already has a handler" in str(error)
    else:
        raise AssertionError("expected a registration error")


def test_command_registry_covers_the_documented_vocabulary() -> None:
    runtime = make_runtime(make_state())

    for command_type in (
        CommandType.START_GAME,
        CommandType.END_TURN,
        CommandType.PLAY_LOOT,
        CommandType.ACTIVATE_TREASURE,
        CommandType.BUY_TREASURE,
        CommandType.ATTACK,
        CommandType.PASS_PRIORITY,
    ):
        assert command_type in runtime.commands.types()
