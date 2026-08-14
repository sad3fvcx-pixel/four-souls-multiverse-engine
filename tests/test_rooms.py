"""
Rooms.

A room is a card that stays face up for the whole table until another replaces
it. `RULES_SPEC.md` §4 lists rooms among the mechanics the engine must support;
what the engine can say about them is limited by what the rules say, and the
comprehensive rulebook supplied for the project has no room section at all. So
this is about the part that is not a room rule but a card rule: a room in play
with a printed "↷" ability is a card that taps for something, and the engine
already knows what that means.
"""

from __future__ import annotations

from conftest import make_definition, make_game, make_instance

from fsme.cards import Ability, CardType
from fsme.commands import Command, CommandType


def room_definition(card_id="test.room", *, effects=({"gain_coins": 3},)):
    return make_definition(
        card_id,
        name="Test Room",
        card_type=CardType.ROOM,
        abilities=(Ability(trigger="on_activate", effects=effects),),
    )


def open_room(state, definition, instance_id="instance:room"):
    room = make_instance(definition, controller=None, owner=None, instance_id=instance_id)

    state.room_area.add_top(room)

    return room


def activate_room(runtime, player=0, index=0, ability=0):
    return runtime.submit(
        Command(
            type=CommandType.ACTIVATE_TREASURE,
            player=player,
            payload={"zone": "room", "index": index, "ability": ability},
        )
    )


def test_a_rooms_ability_can_be_activated() -> None:
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    room = open_room(state, room_definition())

    assert activate_room(runtime).accepted
    assert state.player(0).pennies == 3
    assert room.tapped is True


def test_a_room_taps_like_anything_else_that_taps() -> None:
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    open_room(state, room_definition())

    assert activate_room(runtime).accepted

    again = activate_room(runtime)

    assert again.rejected
    assert "tapped" in again.reason


def test_a_room_without_an_ability_is_refused() -> None:
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    open_room(
        state,
        make_definition("test.plain_room", name="Plain Room", card_type=CardType.ROOM),
    )

    refused = activate_room(runtime)

    assert refused.rejected
    assert "no activated ability" in refused.reason


def test_an_empty_room_area_has_nothing_to_activate() -> None:
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    refused = activate_room(runtime)

    assert refused.rejected
    assert "no room at index" in refused.reason


def test_only_the_active_player_may_use_the_room() -> None:
    """
    COMPREHENSIVE_RULES.md §12: a room belongs to nobody, and the player whose
    turn it is uses it.
    """
    runtime, state = make_game(players=2)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    open_room(state, room_definition())

    assert state.turn.active_player == 0

    refused = activate_room(runtime, player=1)

    assert refused.rejected
    assert "active player" in refused.reason

    assert activate_room(runtime, player=0).accepted
    assert state.player(0).pennies == 3


# ----------------------------------------------------------------------
# The change of rooms
# ----------------------------------------------------------------------


def played_out(runtime, state, player=0) -> None:
    """
    End the turn, answering whatever the end phase asks.
    """
    runtime.submit(Command(type=CommandType.END_PHASE, player=player))
    runtime.submit(Command(type=CommandType.END_TURN, player=player))


def answer(runtime, choice: int) -> None:
    decision = runtime.awaiting_decision

    assert decision is not None

    runtime.submit(
        Command(
            type=CommandType.CHOOSE_TARGET,
            player=decision.player,
            payload={"choices": [choice]},
        )
    )


def stock_room_deck(state, *definitions) -> list:
    rooms = [
        make_instance(
            definition, controller=None, owner=None, instance_id=f"room:deck{index}"
        )
        for index, definition in enumerate(definitions)
    ]

    for room in rooms:
        state.room_deck.add_top(room)

    return rooms


def test_no_room_changes_in_a_turn_where_nothing_died() -> None:
    """
    COMPREHENSIVE_RULES.md §12: the offer comes only after a monster has died.
    """
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    standing = open_room(state, room_definition())
    stock_room_deck(state, room_definition("test.next_room"))

    played_out(runtime, state)

    assert runtime.awaiting_decision is None
    assert standing in state.room_area.cards


def test_the_active_player_may_change_the_room_after_a_kill() -> None:
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    standing = open_room(state, room_definition())
    waiting = stock_room_deck(state, room_definition("test.next_room"))[0]

    runtime.context.apply("kill", [state.active_monsters.cards[0]])
    runtime.run()

    assert state.turn.monster_died is True

    played_out(runtime, state)

    decision = runtime.awaiting_decision

    assert decision is not None
    assert decision.player == 0, "the active player decides"

    answer(runtime, 0)  # yes

    assert standing in state.room_discard.cards
    assert waiting in state.room_area.cards


def test_the_active_player_may_keep_the_room_instead() -> None:
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    standing = open_room(state, room_definition())
    waiting = stock_room_deck(state, room_definition("test.next_room"))[0]

    runtime.context.apply("kill", [state.active_monsters.cards[0]])
    runtime.run()

    played_out(runtime, state)

    assert runtime.awaiting_decision is not None

    answer(runtime, 1)  # no

    assert standing in state.room_area.cards
    assert waiting in state.room_deck.cards


def test_a_table_playing_without_rooms_is_never_asked() -> None:
    """
    Rooms are optional content: a game without them has no room step.
    """
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    runtime.context.apply("kill", [state.active_monsters.cards[0]])
    runtime.run()

    played_out(runtime, state)

    assert runtime.awaiting_decision is None


def test_an_emptied_slot_stays_empty_when_the_deck_has_run_out() -> None:
    """
    "The top card of the room deck" is nothing when there is no top card.
    """
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    standing = open_room(state, room_definition())

    runtime.context.apply("kill", [state.active_monsters.cards[0]])
    runtime.run()

    played_out(runtime, state)

    answer(runtime, 0)

    assert standing in state.room_discard.cards
    assert not state.room_area.cards


def test_the_turn_forgets_the_death_when_it_passes() -> None:
    runtime, state = make_game()
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    runtime.context.apply("kill", [state.active_monsters.cards[0]])
    runtime.run()

    assert state.turn.monster_died is True

    played_out(runtime, state)

    assert state.turn.monster_died is False, "a new turn has seen nothing die"
