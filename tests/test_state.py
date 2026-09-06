"""
GameState holds the whole game and implements none of it.
"""

from __future__ import annotations

from conftest import make_state

from fsme.events import EventQueue
from fsme.stack import Stack, StackItem, StackItemType
from fsme.state import GameState


def test_stack_lives_in_state_and_is_the_stack_type() -> None:
    """
    GAME_STATE.md section 9 puts the stack inside GameState, and there is only
    one stack implementation: the state must not grow a second one of its own.
    """
    state = make_state()

    assert isinstance(state.stack, Stack)
    assert isinstance(state.events, EventQueue)

    assert not hasattr(state, "push")
    assert not hasattr(state, "pop")
    assert not hasattr(state, "reset_stack")


def test_state_is_stable_when_nothing_is_pending() -> None:
    state = make_state()

    assert state.is_stable()

    state.stack.push(StackItem(kind=StackItemType.ENGINE_EFFECT, label="a"))

    assert not state.is_stable()


def test_every_required_zone_exists() -> None:
    """
    GAME_STATE.md section 6 lists the zones a game must track.
    """
    state = GameState()

    for zone in (
        "loot_deck",
        "loot_discard",
        "monster_deck",
        "monster_discard",
        "active_monsters",
        "treasure_deck",
        "treasure_discard",
        "treasure_shop",
        "room_deck",
        "room_area",
    ):
        assert hasattr(state, zone), zone


def test_identifiers_are_deterministic() -> None:
    """
    Two states built the same way allocate the same identifiers.
    """
    first = make_state()
    second = make_state()

    assert [first.ids.allocate("event") for _ in range(3)] == [
        second.ids.allocate("event") for _ in range(3)
    ]
