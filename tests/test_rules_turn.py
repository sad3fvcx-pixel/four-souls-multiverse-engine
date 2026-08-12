"""
Turn structure: start of game, phases, allowances, end of turn.
"""

from __future__ import annotations

from conftest import make_game, make_instance, treasure_definition

from fsme.commands import Command, CommandType
from fsme.events import EventType
from fsme.rules import HAND_LIMIT, STARTING_HAND_SIZE
from fsme.state import GamePhase


def start(runtime):
    return runtime.submit(Command(type=CommandType.START_GAME, player=0))


def end_turn(runtime, player):
    return runtime.submit(Command(type=CommandType.END_TURN, player=player))


def test_starting_deals_hands_and_opens_the_first_turn() -> None:
    runtime, state = make_game()

    start(runtime)

    assert [player.hand_size for player in state.players] == [
        STARTING_HAND_SIZE,
        STARTING_HAND_SIZE,
    ]
    assert state.turn.turn_number == 1
    assert state.turn.active_player == 0
    assert state.turn.phase is GamePhase.LOOT

    types = [event.type for event in runtime.history]

    assert types.index(EventType.GAME_START) < types.index(EventType.TURN_START)


def test_ending_a_turn_passes_the_seat_on() -> None:
    runtime, state = make_game()
    start(runtime)

    assert end_turn(runtime, 0).accepted

    assert state.turn.active_player == 1
    assert state.turn.turn_number == 2
    assert state.turn.phase is GamePhase.LOOT

    types = [event.type for event in runtime.history]

    assert EventType.TURN_END in types
    assert EventType.TURN_CLEANUP in types


def test_the_seat_order_skips_dead_players() -> None:
    runtime, state = make_game(players=3)
    start(runtime)

    state.player(1).kill()

    end_turn(runtime, 0)

    assert state.turn.active_player == 2


def test_a_new_turn_recharges_the_active_player_items() -> None:
    runtime, state = make_game()
    start(runtime)

    card = make_instance(treasure_definition(), controller=1, owner=1)
    card.tapped = True
    state.player(1).treasures.add_top(card)

    end_turn(runtime, 0)

    assert card.tapped is False
    assert EventType.TREASURE_CHARGED in [event.type for event in runtime.history]


def test_ending_a_turn_discards_down_to_the_hand_limit() -> None:
    runtime, state = make_game(loot_cards=40)
    start(runtime)

    player = state.player(0)

    while player.hand_size < HAND_LIMIT + 3:
        player.hand.add_top(state.loot_deck.draw())

    end_turn(runtime, 0)

    assert player.hand_size == HAND_LIMIT
    assert EventType.LOOT_DISCARDED in [event.type for event in runtime.history]


def test_a_turn_grants_one_loot_play_and_one_attack() -> None:
    runtime, state = make_game()
    start(runtime)

    assert state.player(0).attacks_left == 1
    assert state.turn.loot_played == 0

    assert runtime.submit(
        Command(type=CommandType.PLAY_LOOT, player=0, payload={"index": 0})
    ).accepted

    second = runtime.submit(
        Command(type=CommandType.PLAY_LOOT, player=0, payload={"index": 0})
    )

    assert second.rejected
    assert "no loot plays remaining" in second.reason


def test_played_loot_resolves_then_reaches_the_discard_pile() -> None:
    runtime, state = make_game()
    start(runtime)

    player = state.player(0)
    card = player.hand.cards[0]

    runtime.submit(
        Command(type=CommandType.PLAY_LOOT, player=0, payload={"index": 0})
    )

    assert card not in player.hand.cards
    assert card in state.loot_discard.cards
    assert player.pennies == 1

    types = [event.type for event in runtime.history]

    assert types.index(EventType.COINS_GAINED) < types.index(EventType.AFTER_LOOT)


def test_phases_gate_what_may_be_done() -> None:
    """
    A treasure cannot be bought during the loot phase.
    """
    runtime, state = make_game()
    start(runtime)

    state.player(0).pennies = 50

    result = runtime.submit(
        Command(type=CommandType.BUY_TREASURE, player=0, payload={"index": 0})
    )

    assert result.rejected
    assert "loot phase" in result.reason
