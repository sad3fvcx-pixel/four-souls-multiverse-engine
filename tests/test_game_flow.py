"""
A game played through the command interface, start to finish.

Nothing here reaches into GameState to make something happen: every change is
the consequence of a submitted command, which is the property the whole
architecture exists to guarantee.
"""

from __future__ import annotations

from conftest import make_game, make_instance, treasure_definition

from fsme.commands import Command, CommandType
from fsme.events import EventType
from fsme.rules import TREASURE_COST
from fsme.state import GamePhase


def submit(runtime, command_type, player=0, **payload):
    return runtime.submit(
        Command(type=command_type, player=player, payload=payload)
    )


def settle(runtime):
    """
    Answer whatever the game is waiting on, taking the first option.

    A player who dies pays a penalty, and paying it means choosing which loot
    card and which item to lose. A test about the shape of a turn is not about
    which card that was.
    """
    while runtime.awaiting_decision is not None:
        decision = runtime.awaiting_decision

        submit(
            runtime,
            CommandType.CHOOSE_TARGET,
            player=decision.player,
            choices=[0] if decision.options else [],
        )


def test_a_turn_runs_through_every_phase() -> None:
    runtime, state = make_game()

    assert submit(runtime, CommandType.START_GAME).accepted
    assert state.turn.phase is GamePhase.LOOT

    assert submit(runtime, CommandType.PLAY_LOOT, index=0).accepted
    assert submit(runtime, CommandType.END_PHASE).accepted
    assert state.turn.phase is GamePhase.ACTION

    # This attack goes badly: the monster's blow is fatal, and paying for a
    # death ends the turn of whoever paid it, so the turn passes without
    # anybody ending it.
    assert submit(runtime, CommandType.ATTACK, index=0).accepted

    settle(runtime)

    assert state.turn.active_player == 1
    assert state.turn.phase is GamePhase.LOOT
    assert state.player(0).alive, "and everybody heals when a turn ends"


def test_buying_a_treasure_moves_it_and_charges_for_it() -> None:
    runtime, state = make_game()

    submit(runtime, CommandType.START_GAME)
    submit(runtime, CommandType.END_PHASE)

    player = state.player(0)
    player.pennies = TREASURE_COST + 3

    offered = state.treasure_shop.cards[0]

    assert submit(runtime, CommandType.BUY_TREASURE, index=0).accepted

    assert offered in player.treasures.cards
    assert offered.owner == 0
    assert offered.controller == 0
    assert player.pennies == 3
    assert EventType.TREASURE_BOUGHT in [event.type for event in runtime.history]


def test_buying_without_enough_money_is_refused() -> None:
    runtime, state = make_game()

    submit(runtime, CommandType.START_GAME)
    submit(runtime, CommandType.END_PHASE)

    result = submit(runtime, CommandType.BUY_TREASURE, index=0)

    assert result.rejected
    assert "costs" in result.reason


def test_an_item_may_be_activated_once_per_turn_and_recharges_next_turn() -> None:
    runtime, state = make_game()

    submit(runtime, CommandType.START_GAME)

    card = make_instance(
        treasure_definition("test.tap", effects=({"gain_coins": 2},)),
        controller=0,
        owner=0,
        instance_id="instance:tap",
    )
    state.player(0).treasures.add_top(card)

    assert submit(runtime, CommandType.ACTIVATE_TREASURE, index=0).accepted
    assert card.tapped is True
    assert state.player(0).pennies == 2

    again = submit(runtime, CommandType.ACTIVATE_TREASURE, index=0)

    assert again.rejected
    assert "already tapped" in again.reason

    submit(runtime, CommandType.END_PHASE)
    submit(runtime, CommandType.END_TURN)
    submit(runtime, CommandType.END_PHASE, player=1)
    submit(runtime, CommandType.END_TURN, player=1)

    assert state.turn.active_player == 0
    assert card.tapped is False


def test_several_turns_stay_stable() -> None:
    runtime, state = make_game(loot_cards=40, monsters=2)

    submit(runtime, CommandType.START_GAME)

    for _ in range(6):
        if state.game_over:
            break

        player = state.turn.active_player

        submit(runtime, CommandType.PLAY_LOOT, player=player, index=0)
        submit(runtime, CommandType.END_PHASE, player=player)
        submit(runtime, CommandType.ATTACK, player=player, index=0)

        settle(runtime)

        submit(runtime, CommandType.END_TURN, player=player)

        settle(runtime)

        assert runtime.is_stable()

    assert all(result.accepted or result.reason for result in runtime.command_log)


def test_a_game_runs_to_victory_without_intervention() -> None:
    """
    Stage 3 exit criterion: a game of several turns reaches its end through
    commands alone. Nothing here writes to GameState.
    """
    from test_combat import FixedRNG

    runtime, state = make_game(
        loot_cards=60, monsters=8, rng=FixedRNG([6] * 200)
    )

    submit(runtime, CommandType.START_GAME)

    turns = 0

    while not state.game_over and turns < 40:
        player = state.turn.active_player

        if player == 0:
            submit(runtime, CommandType.END_PHASE, player=player)
            submit(runtime, CommandType.ATTACK, player=player, index=0)

        submit(runtime, CommandType.END_TURN, player=player)
        turns += 1

        assert runtime.is_stable()

    assert state.game_over is True
    assert state.winner == 0
    assert state.player(0).soul_count >= state.souls_to_win

    types = [event.type for event in runtime.history]

    assert EventType.WINNER_DECLARED in types
    assert types[-1] is EventType.GAME_END


def test_the_same_seed_produces_the_same_game_through_commands() -> None:
    def play(seed: int):
        runtime, state = make_game(seed=seed, loot_cards=40, monsters=2)

        submit(runtime, CommandType.START_GAME)

        for _ in range(4):
            if state.game_over:
                break

            player = state.turn.active_player

            submit(runtime, CommandType.PLAY_LOOT, player=player, index=0)
            submit(runtime, CommandType.END_PHASE, player=player)
            submit(runtime, CommandType.ATTACK, player=player, index=0)
            submit(runtime, CommandType.END_TURN, player=player)

        return (
            [(p.hp, p.pennies, p.soul_count, p.alive) for p in state.players],
            state.ids.counter,
            [(event.event_id, str(event.type)) for event in runtime.history],
        )

    assert play(2024) == play(2024)
    assert play(2024) != play(9999)
