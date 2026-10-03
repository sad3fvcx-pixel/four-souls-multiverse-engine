"""
Turn structure: start of game, phases, allowances, end of turn.
"""

from __future__ import annotations

from conftest import make_definition, make_game, make_instance, treasure_definition

from fsme.cards import Ability, CardType
from fsme.commands import Command, CommandType
from fsme.events import EventType
from fsme.rules import HAND_LIMIT, STARTING_COINS, STARTING_HAND_SIZE
from fsme.stack import ADVANCE_TURN, DISCARD_TO_HAND_LIMIT, StackItem, StackItemType
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


def _scheduled(state) -> list[str]:
    """
    The engine's own turn-ending objects waiting on the stack, bottom first.
    """
    return [
        item.label
        for item in state.stack
        if item.label in (ADVANCE_TURN, DISCARD_TO_HAND_LIMIT)
    ]


def _ends_the_turn(state, effects, *, targets=()) -> None:
    """
    Give the active player a treasure that answers the end of their turn.
    """
    state.player(0).treasures.add_top(
        make_instance(
            make_definition(
                "test.parting_shot",
                name="Parting Shot",
                card_type=CardType.TREASURE,
                abilities=(
                    Ability(
                        trigger="turn_end", targets=tuple(targets), effects=effects
                    ),
                ),
            ),
            controller=0,
            owner=0,
            instance_id="instance:parting_shot",
        )
    )


def test_ending_the_turn_from_an_ability_schedules_both_halves() -> None:
    """
    The effect that ends a turn puts the discard and the advance on the stack,
    the discard above so that it resolves first.
    """
    runtime, state = make_game()
    start(runtime)

    runtime.context.apply("end_turn", [])

    assert _scheduled(state) == [ADVANCE_TURN, DISCARD_TO_HAND_LIMIT]


def test_a_turn_already_ending_is_not_ended_again() -> None:
    """
    An ability that answers the end of the turn by ending it changes nothing.

    The turn is already being passed when "at the end of your turn" fires, so a
    second advance is not a second ending — it is the same ending twice. It
    passed the seat twice: the next player was dealt two opening loot cards
    instead of one and the turn number went up by two.
    """
    runtime, state = make_game(loot_cards=40)
    _ends_the_turn(state, ({"effect": "end_turn"},))
    start(runtime)

    opening = state.player(1).hand_size

    end_turn(runtime, 0)

    assert state.turn.turn_number == 2
    assert state.turn.active_player == 1
    assert state.player(1).hand_size == opening + 1
    assert _scheduled(state) == []


def test_ending_a_turn_twice_in_one_ability_ends_it_once() -> None:
    """
    Two instructions to end the turn in one ability are one ending.
    """
    runtime, state = make_game()
    start(runtime)

    runtime.context.apply("end_turn", [])
    runtime.context.apply("end_turn", [])

    assert _scheduled(state) == [ADVANCE_TURN, DISCARD_TO_HAND_LIMIT]

    runtime.run()

    assert state.turn.turn_number == 2
    assert state.turn.active_player == 1


def test_an_extra_turn_promised_at_the_end_is_still_taken() -> None:
    """
    A second advance took back the extra turn the moment it was granted: the
    first one kept the seat, the second passed it, and the promised turn was
    over before it began.
    """
    runtime, state = make_game()
    _ends_the_turn(
        state,
        (
            {"effect": "take_extra_turn", "target": "controller"},
            {"effect": "end_turn"},
        ),
    )
    start(runtime)

    end_turn(runtime, 0)

    assert state.turn.active_player == 0
    assert state.turn.turn_number == 2


def test_a_cancelled_ending_may_be_scheduled_again() -> None:
    """
    "Cancel everything that hasn't resolved" reaches the turn-ending objects,
    and O. The Fool says that and then ends the turn.

    Once they are off the stack the turn is not ending any more, so the next
    instruction to end it has to be obeyed. Remembering that the end had been
    announced, rather than asking the stack, would leave this game with no way
    to pass the seat at all.
    """
    runtime, state = make_game()
    _ends_the_turn(
        state,
        (
            {"effect": "cancel_stack", "target": "doomed"},
            {"effect": "end_turn"},
        ),
        targets=({"all_stack": {"as": "doomed"}},),
    )
    start(runtime)

    end_turn(runtime, 0)

    assert state.turn.turn_number == 2
    assert state.turn.active_player == 1
    assert _scheduled(state) == []


def test_the_turn_ending_is_recognised_by_the_stack_and_not_by_a_card() -> None:
    """
    What stops a second ending is the object waiting on the stack, whatever put
    it there: an advance with no card and no ability behind it counts.
    """
    runtime, state = make_game()
    start(runtime)

    runtime.context.push(
        StackItem(
            kind=StackItemType.ENGINE_EFFECT,
            label=ADVANCE_TURN,
            controller=0,
        )
    )

    assert runtime.context.apply("end_turn", []) == 0
    assert _scheduled(state) == [ADVANCE_TURN]


def _announcements(runtime) -> list[str]:
    """
    Every turn-ending announcement, in the order the engine made them.
    """
    said: list[str] = []

    for event_type in (EventType.TURN_END, EventType.TURN_CLEANUP):
        runtime.subscribe(
            event_type,
            lambda event, name=str(event_type): said.append(name),
        )

    return said


def test_a_turn_ended_by_a_card_enters_its_end_phase() -> None:
    """
    §3.3 step 1: an effect that ends a turn jumps straight into the end phase.

    It used to jump straight to passing the seat instead, so the phase never
    became `end` and nothing announced the turn's end. Measured before this was
    written: 1072 of 2693 turns across forty four-player games, two turns in
    five, ended with no `turn_end` at all.
    """
    runtime, state = make_game()
    start(runtime)

    said = _announcements(runtime)

    runtime.context.apply("end_turn", [])

    assert state.turn.phase is GamePhase.END, "on the way in, before anything resolves"

    runtime.run()

    assert said == [str(EventType.TURN_END), str(EventType.TURN_CLEANUP)]


def test_a_card_answering_the_end_of_a_turn_hears_one_ended_by_a_card() -> None:
    """
    The whole point of the announcement: sixteen shipped cards say "at the end
    of your turn", and a turn ended this way never reached them.
    """
    runtime, state = make_game()

    state.player(0).treasures.add_top(
        make_instance(
            make_definition(
                "test.last_word",
                name="Last Word",
                card_type=CardType.TREASURE,
                abilities=(
                    Ability(
                        trigger="turn_end",
                        effects=({"effect": "gain_coins", "amount": 7},),
                    ),
                ),
            ),
            controller=0,
            owner=0,
            instance_id="instance:last_word",
        )
    )

    start(runtime)

    before = state.player(0).pennies

    runtime.context.apply("end_turn", [])
    runtime.run()

    assert state.player(0).pennies == before + 7


def test_the_end_of_a_turn_is_announced_once_however_often_it_is_ended() -> None:
    """
    The phase is the record that the end has been announced.

    A card may answer the end of the turn by cancelling the ending and ending it
    again — "Parting Shot" below is that card — and announcing the end afresh
    each time calls it again, unbounded, until the engine stops itself. The
    scheduling still asks the stack, so a cancelled ending is still
    rescheduled; only the announcement is once.
    """
    runtime, state = make_game()
    _ends_the_turn(
        state,
        (
            {"effect": "cancel_stack", "target": "doomed"},
            {"effect": "end_turn"},
        ),
        targets=({"all_stack": {"as": "doomed"}},),
    )
    start(runtime)

    said = _announcements(runtime)

    end_turn(runtime, 0)

    assert said.count(str(EventType.TURN_END)) == 1
    assert state.turn.turn_number == 2, "and the seat still passed"


def test_a_turn_the_player_ends_is_announced_by_the_handler_alone() -> None:
    """
    The other path is untouched: it announces its own end exactly once, and the
    effect no longer adds a second announcement on top of it.
    """
    runtime, state = make_game()
    start(runtime)

    said = _announcements(runtime)

    end_turn(runtime, 0)

    assert said.count(str(EventType.TURN_END)) == 1
    assert said.count(str(EventType.TURN_CLEANUP)) == 1


def end_phase(runtime, player):
    return runtime.submit(Command(type=CommandType.END_PHASE, player=player))


def _owes_an_attack(runtime) -> None:
    """
    Put an unpaid "must attack" debt on the active player.

    Everything a debt needs to be payable is true here — the player is alive
    and able to attack, and there is a monster on the board to attack — so the
    only thing left to decide the answer is the phase.
    """
    runtime.context.apply("require_attack", [], times=1)


def test_a_debt_incurred_in_the_end_phase_does_not_hold_the_turn_open() -> None:
    """
    A debt nobody can pay is not a debt, and the end phase is where attacking
    stops: there is no attack left in the turn to pay with, and a turn does not
    go back to its action phase.

    Left as it was, the game stopped. The debt refused to let the turn end, the
    phase could not be ended either because it was already the last one, and
    no attack was offered to pay with: two of sixty seeded two-player games
    reached that dead end and had no move at all.
    """
    runtime, state = make_game()
    start(runtime)

    assert end_phase(runtime, 0).accepted, "the loot phase ends"
    assert end_phase(runtime, 0).accepted, "and so does the action phase"
    assert state.turn.phase is GamePhase.END

    _owes_an_attack(runtime)

    assert state.turn.obligations, "the debt is still recorded"
    assert end_turn(runtime, 0).accepted
    assert state.turn.turn_number == 2, "and the seat passed"


def test_a_debt_still_holds_the_turn_open_where_it_can_be_paid() -> None:
    """
    The other side of it: in the action phase the debt bites, as it always has.
    """
    runtime, state = make_game()
    start(runtime)

    assert end_phase(runtime, 0).accepted
    assert state.turn.phase is GamePhase.ACTION

    _owes_an_attack(runtime)

    refused = end_turn(runtime, 0)

    assert not refused.accepted
    assert "must still attack" in str(refused.reason)
    assert not end_phase(runtime, 0).accepted, "nor may the player leave the phase"


def test_a_debt_owed_before_the_action_phase_still_holds_the_turn_open() -> None:
    """
    The narrowing is to the end phase alone, not to "anywhere but the action
    phase": a turn in its loot phase is still going to reach its action phase,
    so the debt there is one the player can still pay.
    """
    runtime, state = make_game()
    start(runtime)

    assert state.turn.phase is GamePhase.LOOT

    _owes_an_attack(runtime)

    refused = end_turn(runtime, 0)

    assert not refused.accepted
    assert "must still attack" in str(refused.reason)
