"""
Pending player decisions.

An ability that says "choose a player" stops the engine until somebody chooses,
then carries on from the exact operation it stopped on.
"""

from __future__ import annotations

import pytest
from conftest import make_game, make_instance, treasure_definition

from fsme.commands import Command, CommandType
from fsme.rules import STARTING_COINS
from fsme.runtime.ability_context import CHOSEN_AT
from fsme.state import DecisionKind
from fsme.util.errors import EngineError


def start(runtime):
    return runtime.submit(Command(type=CommandType.START_GAME, player=0))


def give(state, player_id, effects, card_id="test.chooser"):
    card = make_instance(
        treasure_definition(card_id, effects=effects),
        controller=player_id,
        owner=player_id,
        instance_id=f"instance:{card_id}",
    )
    state.player(player_id).treasures.add_top(card)

    return card


def activate(runtime, player=0, index=0):
    return runtime.submit(
        Command(
            type=CommandType.ACTIVATE_TREASURE, player=player, payload={"index": index}
        )
    )


def choose(runtime, player, *indices):
    return runtime.submit(
        Command(
            type=CommandType.CHOOSE_TARGET,
            player=player,
            payload={"choices": list(indices)},
        )
    )


def test_an_ability_stops_to_ask_and_resumes_afterwards() -> None:
    runtime, state = make_game(players=3)
    start(runtime)

    give(
        state,
        0,
        ({"effect": "deal_damage", "amount": 1, "target": "target_player"},),
    )

    activate(runtime)

    decision = runtime.awaiting_decision

    assert decision is not None
    assert decision.kind is DecisionKind.CHOOSE_PLAYER
    assert decision.player == 0
    assert len(decision.options) == 3
    assert [player.hp for player in state.players] == [2, 2, 2]

    victim = decision.options.index(state.player(2))

    assert choose(runtime, 0, victim).accepted

    assert [player.hp for player in state.players] == [2, 2, 1]
    assert runtime.awaiting_decision is None
    assert runtime.is_stable()


def test_the_engine_waits_and_refuses_everything_else() -> None:
    runtime, state = make_game(players=3)
    start(runtime)

    give(
        state,
        0,
        ({"effect": "deal_damage", "amount": 1, "target": "target_player"},),
    )
    activate(runtime)

    result = runtime.submit(Command(type=CommandType.END_TURN, player=0))

    assert result.rejected
    assert "still choosing" in result.reason
    assert not state.is_stable()


def test_only_the_asked_player_may_answer() -> None:
    runtime, state = make_game(players=3)
    start(runtime)

    give(
        state,
        0,
        ({"effect": "deal_damage", "amount": 1, "target": "target_player"},),
    )
    activate(runtime)

    result = choose(runtime, 1, 0)

    assert result.rejected
    assert "is choosing" in result.reason


def test_an_option_outside_the_offer_is_refused() -> None:
    runtime, state = make_game(players=3)
    start(runtime)

    give(
        state,
        0,
        ({"effect": "deal_damage", "amount": 1, "target": "target_player"},),
    )
    activate(runtime)

    result = choose(runtime, 0, 99)

    assert result.rejected
    assert "no option at index" in result.reason
    assert runtime.awaiting_decision is not None


def test_the_wrong_number_of_options_is_refused() -> None:
    runtime, state = make_game(players=3)
    start(runtime)

    give(
        state,
        0,
        ({"effect": "deal_damage", "amount": 1, "target": "target_player"},),
    )
    activate(runtime)

    result = choose(runtime, 0, 0, 1)

    assert result.rejected
    assert "takes between" in result.reason


def test_a_single_option_is_taken_without_asking() -> None:
    """
    One candidate is not a choice, so the game does not stop to confirm it.
    """
    runtime, state = make_game(players=2)
    start(runtime)

    state.player(1).kill()

    give(
        state,
        0,
        ({"effect": "deal_damage", "amount": 1, "target": "target_player"},),
    )
    activate(runtime)

    assert runtime.awaiting_decision is None
    assert state.player(0).hp == 1


def test_effects_before_the_question_have_already_happened() -> None:
    """
    Resumption continues from the operation that asked, not from the start.
    """
    runtime, state = make_game(players=3)
    start(runtime)

    give(
        state,
        0,
        (
            {"gain_coins": 4},
            {"effect": "deal_damage", "amount": 1, "target": "target_player"},
            {"gain_coins": 1},
        ),
    )

    activate(runtime)

    assert state.player(0).pennies == STARTING_COINS + 4

    choose(runtime, 0, 0)

    assert state.player(0).pennies == STARTING_COINS + 5


def test_a_monster_may_be_chosen() -> None:
    runtime, state = make_game(monsters=2)
    start(runtime)

    give(
        state,
        0,
        ({"effect": "deal_damage", "amount": 1, "target": "target_monster"},),
    )
    activate(runtime)

    decision = runtime.awaiting_decision

    assert decision is not None
    assert decision.kind is DecisionKind.CHOOSE_MONSTER
    assert len(decision.options) == 2

    choose(runtime, 0, 1)

    assert decision.options[1].hp == 1
    assert decision.options[0].hp == 2


def test_a_decision_survives_in_the_game_state() -> None:
    """
    GAME_STATE.md requires the whole game to live in GameState, and a game
    saved mid-question has to reload mid-question.
    """
    runtime, state = make_game(players=3)
    start(runtime)

    give(
        state,
        0,
        ({"effect": "deal_damage", "amount": 1, "target": "target_player"},),
    )
    activate(runtime)

    assert state.pending_decision is not None
    assert state.pending_decision.continuation is not None
    assert state.pending_decision.decision_id.startswith("decision:")


def two_modes(first, second, *, as_name="picked"):
    """
    One "choose one" whose two modes pay different amounts.
    """
    return (
        {
            "choose": [
                {"description": first[0], "effects": [{"gain_coins": first[1]}]},
                {"description": second[0], "effects": [{"gain_coins": second[1]}]},
            ],
            "as": as_name,
        },
    )


def coins_after(effects, pick, *, players=2):
    """
    Play a card that offers a choice, take the option at `pick`, count the coins.
    """
    runtime, state = make_game(players=players)
    start(runtime)
    give(state, 0, effects)

    before = state.player(0).pennies

    activate(runtime)

    decision = runtime.awaiting_decision

    assert decision is not None, "the card was supposed to ask"

    offered = list(decision.options)

    assert choose(runtime, 0, pick).accepted

    return state.player(0).pennies - before, offered


def test_a_mode_is_taken_by_where_it_was_offered() -> None:
    """
    Two modes described alike are still two modes.

    The answer travels as a position, is checked as a position, and used to be
    turned back into one by looking the description up among the descriptions —
    so two modes reading the same made the second unreachable: whatever the
    player answered, `['Same', 'Same'].index('Same')` is nought and the first
    mode ran. Nothing said so. The card was clean, the form saved it, and the
    option was simply never the one that happened.
    """
    gained, offered = coins_after(two_modes(("Same", 1), ("Same", 7)), 1)

    assert offered == ["Same", "Same"], "the player is offered what the card says"
    assert gained == 7, "the second mode is the one that was taken"


def test_modes_told_apart_are_still_told_apart() -> None:
    """
    The ordinary case, which is what the fix must leave alone.
    """
    for pick, expected in ((0, 1), (1, 7)):
        gained, offered = coins_after(two_modes(("Gain 1", 1), ("Gain 7", 7)), pick)

        assert offered == ["Gain 1", "Gain 7"]
        assert gained == expected


def test_modes_with_nothing_written_on_them_are_numbered() -> None:
    """
    A mode with no description is offered as its place in the list, and that
    was always reachable — the numbering made it unique. Kept here because it
    is the case the checker refuses and the one that never broke.
    """
    effects = (
        {
            "choose": [
                {"effects": [{"gain_coins": 1}]},
                {"effects": [{"gain_coins": 7}]},
            ]
        },
    )

    gained, offered = coins_after(effects, 1)

    assert offered == ["mode 1", "mode 2"]
    assert gained == 7


def test_each_choice_of_an_ability_reads_its_own_answer() -> None:
    """
    Two questions in one ability, answered one after the other.

    The position is kept under the name the answer is bound to, so the second
    question cannot be resolved with the first one's number.
    """
    runtime, state = make_game(players=2)
    start(runtime)
    give(
        state,
        0,
        two_modes(("A1", 1), ("A2", 2), as_name="first")
        + two_modes(("B1", 10), ("B2", 20), as_name="second"),
    )

    before = state.player(0).pennies

    activate(runtime)

    for pick, expected in ((0, ["A1", "A2"]), (1, ["B1", "B2"])):
        decision = runtime.awaiting_decision

        assert decision is not None
        assert list(decision.options) == expected

        assert choose(runtime, 0, pick).accepted

    assert state.player(0).pennies - before == 1 + 20


def test_two_choices_under_one_name_are_still_refused() -> None:
    """
    Asking twice under one name has always been a mistake and is still named as
    one: the second question finds the first answer already bound and an answer
    that is not among its own modes.

    Here so that resolving by position cannot quietly turn it into a mode: the
    number would be a perfectly good index into the wrong list.
    """
    runtime, state = make_game(players=2)
    start(runtime)
    give(
        state,
        0,
        two_modes(("A1", 1), ("A2", 2), as_name="same")
        + two_modes(("B1", 10), ("B2", 20), as_name="same"),
    )

    activate(runtime)

    decision = runtime.awaiting_decision

    assert decision is not None

    with pytest.raises(EngineError) as raised:
        choose(runtime, 0, 1)

    assert "not one of this card's modes" in str(raised.value)


def test_a_card_may_not_keep_a_result_where_a_choice_is_remembered() -> None:
    """
    One name, refused in one place, for one reason.

    A card names what it keeps, and the engine reads which option was taken out
    of the same dictionary. Left open, a card storing a number under that name
    ended resolution with `'int' object is not iterable` — a Python error naming
    nothing an author could act on. Refused where the name is written instead,
    and named.

    Only this name. The engine's other private names were reachable this way
    before any of this existed, and closing them is a decision about the whole
    namespace rather than about choosing a mode.
    """
    runtime, state = make_game(players=2)
    start(runtime)
    give(
        state,
        0,
        ({"effect": "gain_coins", "amount": 1, "store": CHOSEN_AT},),
    )

    with pytest.raises(EngineError) as raised:
        activate(runtime)

    assert CHOSEN_AT in str(raised.value)
    assert "where the engine remembers a choice" in str(raised.value)


def test_a_card_may_still_keep_a_result_under_its_own_name() -> None:
    runtime, state = make_game(players=2)
    start(runtime)
    give(state, 0, ({"effect": "gain_coins", "amount": 1, "store": "gained"},))

    assert activate(runtime).accepted
