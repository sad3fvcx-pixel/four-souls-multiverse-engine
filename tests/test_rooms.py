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


def test_any_player_may_use_the_room_they_are_all_standing_in() -> None:
    """
    A room belongs to nobody, so it is not one player's item.
    """
    runtime, state = make_game(players=2)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    open_room(state, room_definition())

    assert activate_room(runtime, player=1).accepted
    assert state.player(1).pennies == 3
    assert state.player(0).pennies == 0
