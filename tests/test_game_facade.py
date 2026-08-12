"""
The Game facade is the whole public surface of the engine.
"""

from __future__ import annotations

from conftest import loot_definition, monster_definition

from fsme.cards import CardInstance
from fsme.commands import CommandType
from fsme.events import Event, EventType
from fsme.game import Game
from fsme.state import GamePhase, GameState, PlayerState


def build_game(*, players: int = 2, seed: int = 5) -> Game:
    state = GameState(seed=seed)

    for index in range(players):
        state.add_player(PlayerState(player_id=index, name=f"player{index}"))

    for index in range(12):
        state.loot_deck.add_top(
            CardInstance(
                definition=loot_definition(f"test.loot{index}"),
                instance_id=f"loot:{index}",
            )
        )

    state.active_monsters.add_top(
        CardInstance(
            definition=monster_definition("test.monster"),
            instance_id="monster:0",
            controller=None,
            owner=None,
        )
    )

    return Game(state)


def test_a_game_is_played_entirely_through_the_facade() -> None:
    game = build_game()

    assert game.start().accepted
    assert game.state.turn.phase is GamePhase.LOOT

    assert game.act(CommandType.PLAY_LOOT, 0, index=0).accepted
    assert game.act(CommandType.END_PHASE, 0).accepted
    assert game.act(CommandType.ATTACK, 0, index=0).accepted
    assert game.act(CommandType.END_TURN, 0).accepted

    assert game.state.turn.active_player == 1
    assert game.is_over is False
    assert game.winner is None


def test_observers_see_events_without_touching_the_game() -> None:
    game = build_game()

    seen: list[Event] = []
    game.subscribe(EventType.TURN_START, seen.append)

    game.start()

    assert len(seen) == 1
    assert seen[0].type is EventType.TURN_START


def test_the_facade_owns_no_state_of_its_own() -> None:
    """
    An earlier Game object kept its own stack beside the one in GameState.
    There is exactly one game, so there is exactly one of everything in it.
    """
    game = build_game()

    assert game.state is game.runtime.state
    assert not hasattr(game, "stack")
    assert not hasattr(game, "commands")


def test_the_facade_reports_rejections_rather_than_raising() -> None:
    game = build_game()
    game.start()

    result = game.act(CommandType.END_TURN, 1)

    assert result.rejected
    assert result.reason
    assert game.command_log[-1] is result
