"""
Turn structure: start of game, phases, allowances, end of turn.
"""

from __future__ import annotations

from conftest import make_definition, make_game, make_instance, treasure_definition

from fsme.cards import Ability, CardType
from fsme.commands import Command, CommandType
from fsme.events import EventType
from fsme.rules import HAND_LIMIT, STARTING_COINS, STARTING_HAND_SIZE
from fsme.state import GamePhase


def start(runtime):
    return runtime.submit(Command(type=CommandType.START_GAME, player=0))


def end_turn(runtime, player):
    return runtime.submit(Command(type=CommandType.END_TURN, player=player))


def test_starting_deals_hands_and_opens_the_first_turn() -> None:
    runtime, state = make_game()

    start(runtime)

    # Everybody is dealt a hand, and the first player has already looted:
    # COMPREHENSIVE_RULES.md §3.1 ends the start phase by drawing one.
    assert [player.hand_size for player in state.players] == [
        STARTING_HAND_SIZE + 1,
        STARTING_HAND_SIZE,
    ]
    assert state.turn.turn_number == 1
    assert state.turn.active_player == 0


def test_starting_deals_three_cents_to_everybody() -> None:
    """
    COMPREHENSIVE_RULES.md §2: "Each player is dealt 3 loot cards and 3¢."

    The loot was dealt from the first version of setup and the coins were not,
    so every game FSME played began three cents short. It is a small number
    and it is not a small change: the first purchase moves later in every
    game, and every statistic measured from those games moves with it.
    """
    runtime, state = make_game()

    assert [player.pennies for player in state.players] == [0, 0]

    start(runtime)

    assert [player.pennies for player in state.players] == [
        STARTING_COINS,
        STARTING_COINS,
    ]


def test_the_cents_are_dealt_at_every_table_size() -> None:
    for players in (1, 2, 3, 4):
        runtime, state = make_game(players=players)

        start(runtime)

        assert all(
            player.pennies >= STARTING_COINS for player in state.players
        ), f"a table of {players} did not all get their cents"
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


def test_a_dead_player_is_back_in_time_for_their_turn() -> None:
    """
    COMPREHENSIVE_RULES.md §3.3 and §10: everybody heals at the end of a turn,
    and that is when whoever died comes back. Nobody is skipped, because by the
    time the turn passes there is nobody left to skip.
    """
    runtime, state = make_game(players=3)
    start(runtime)

    state.player(1).kill()

    end_turn(runtime, 0)

    assert state.player(1).alive
    assert state.player(1).hp == state.player(1).max_hp
    assert state.turn.active_player == 1


def test_a_new_turn_recharges_the_active_player_items() -> None:
    runtime, state = make_game()
    start(runtime)

    card = make_instance(treasure_definition(), controller=1, owner=1)
    card.tapped = True
    state.player(1).treasures.add_top(card)

    end_turn(runtime, 0)

    assert card.tapped is False
    assert EventType.TREASURE_CHARGED in [event.type for event in runtime.history]


def test_ending_a_turn_asks_which_cards_to_discard() -> None:
    """
    A player over the hand limit chooses what to lose, and the turn does not
    pass until they have.
    """
    runtime, state = make_game(loot_cards=40)
    start(runtime)

    player = state.player(0)

    while player.hand_size < HAND_LIMIT + 3:
        player.hand.add_top(state.loot_deck.draw())

    end_turn(runtime, 0)

    decision = runtime.awaiting_decision

    assert decision is not None
    assert decision.player == 0
    assert decision.minimum == 3
    assert decision.maximum == 3
    assert player.hand_size == HAND_LIMIT + 3
    assert state.turn.active_player == 0

    kept = [card for index, card in enumerate(player.hand.cards) if index > 2]

    runtime.submit(
        Command(
            type=CommandType.CHOOSE_TARGET,
            player=0,
            payload={"choices": [0, 1, 2]},
        )
    )

    assert player.hand_size == HAND_LIMIT
    assert player.hand.cards == kept
    assert state.turn.active_player == 1
    assert EventType.LOOT_DISCARDED in [event.type for event in runtime.history]


def test_a_hand_within_the_limit_ends_the_turn_at_once() -> None:
    runtime, state = make_game()
    start(runtime)

    end_turn(runtime, 0)

    assert runtime.awaiting_decision is None
    assert state.turn.active_player == 1


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

    # What the card pays, not what the player holds: they were dealt three
    # cents at setup, and this test is about the card.
    before = player.pennies

    runtime.submit(
        Command(type=CommandType.PLAY_LOOT, player=0, payload={"index": 0})
    )

    assert card not in player.hand.cards
    assert card in state.loot_discard.cards
    assert player.pennies == before + 1

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


def _fill_hand_to(state, seat: int, size: int) -> None:
    """
    Put the player's hand at exactly this many cards.
    """
    player = state.player(seat)

    while player.hand_size < size:
        player.hand.add_top(state.loot_deck.draw())

    while player.hand_size > size:
        state.loot_discard.add_top(player.hand.draw())


def test_cards_drawn_during_the_end_phase_are_still_discarded() -> None:
    """
    §3.3 puts "at the end of your turn" effects at step 1 and the discard at
    step 3, so a card that draws in step 1 is a card that has to be discarded
    in step 3.

    The hand is at the limit when the end phase opens, so nothing looks like it
    needs trimming. Then a treasure triggered by the end of the turn draws two,
    and the answer changes. Deciding how many to discard when the phase opened
    would leave the player carrying twelve cards into somebody else's turn —
    which is what happened, in two turns out of 4318 measured.
    """
    runtime, state = make_game(loot_cards=40)
    start(runtime)

    player = state.player(0)

    generous = make_instance(
        make_definition(
            "test.parting_gift",
            name="Parting Gift",
            card_type=CardType.TREASURE,
            abilities=(
                Ability(trigger="turn_end", effects=({"draw_loot": 2},)),
            ),
        ),
        controller=0,
        owner=0,
        instance_id="instance:parting",
    )
    player.treasures.add_top(generous)

    _fill_hand_to(state, 0, HAND_LIMIT)

    end_turn(runtime, 0)

    decision = runtime.awaiting_decision

    assert decision is not None, "the two cards drawn at the end have to go"
    assert decision.player == 0
    assert decision.minimum == 2
    assert player.hand_size == HAND_LIMIT + 2

    runtime.submit(
        Command(type=CommandType.CHOOSE_TARGET, player=0, payload={"choices": [0, 1]})
    )

    assert player.hand_size == HAND_LIMIT
    assert state.turn.active_player == 1


def test_a_turn_ended_by_a_card_still_trims_the_hand() -> None:
    """
    A turn ended by an effect is still a turn that ended.

    Nearly two turns in five end this way rather than by the active player
    saying so — a card that ends the turn, or the death penalty, which ends the
    active player's turn as its last clause. The hand limit belongs to all of
    them.
    """
    runtime, state = make_game(loot_cards=40)
    start(runtime)

    player = state.player(0)
    _fill_hand_to(state, 0, HAND_LIMIT + 2)

    runtime.context.apply("end_turn", [])
    runtime.run()

    decision = runtime.awaiting_decision

    assert decision is not None
    assert decision.player == 0
    assert decision.minimum == 2

    runtime.submit(
        Command(type=CommandType.CHOOSE_TARGET, player=0, payload={"choices": [0, 1]})
    )

    assert player.hand_size == HAND_LIMIT
    assert state.turn.active_player == 1


def test_a_hand_within_the_limit_is_not_asked_about_twice() -> None:
    """
    The object that asks *how many* pushes nothing when the answer is none.
    """
    runtime, state = make_game()
    start(runtime)

    runtime.context.apply("end_turn", [])
    runtime.run()

    assert runtime.awaiting_decision is None
    assert state.turn.active_player == 1
