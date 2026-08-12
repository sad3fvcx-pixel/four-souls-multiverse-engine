"""
Pending player decisions.

An ability that says "choose a player" stops the engine until somebody chooses,
then carries on from the exact operation it stopped on.
"""

from __future__ import annotations

from conftest import make_game, make_instance, treasure_definition

from fsme.commands import Command, CommandType
from fsme.state import DecisionKind


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

    assert state.player(0).pennies == 4

    choose(runtime, 0, 0)

    assert state.player(0).pennies == 5


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
