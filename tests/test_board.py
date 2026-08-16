"""
Cards that live on the table: items, curses and rooms.

What counts as "in play" is one list, shared by triggered abilities and static
modifiers, so a card cannot be live for one and dead for the other.
"""

from __future__ import annotations

from typing import Any

import pytest
from conftest import make_definition, make_game, make_instance

from fsme.cards import Ability, CardInstance, CardType, Static
from fsme.commands import Command, CommandType
from fsme.effects import EffectExecutionError
from fsme.events import EventType
from fsme.rules import ATTACK, cards_in_play
from fsme.rules.statics import bonus


def item(card_id="test.item", *, tags=(), card_type=CardType.TREASURE, **kwargs):
    return make_definition(
        card_id, card_type=card_type, tags=frozenset(tags), **kwargs
    )


def started(**kwargs):
    runtime, state = make_game(**kwargs)
    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    return runtime, state


def equip(state, player_id, definition, instance_id="instance:1"):
    card = make_instance(
        definition, controller=player_id, owner=player_id, instance_id=instance_id
    )
    state.player(player_id).treasures.add_top(card)

    return card


# ----------------------------------------------------------------------
# Items
# ----------------------------------------------------------------------


def test_an_item_can_be_stolen() -> None:
    runtime, state = started()

    card = equip(state, 1, item("test.loot_bag"))

    runtime.context._set_actor(0)
    runtime.context.apply("steal_treasure", [card])
    runtime.run()

    assert card in state.player(0).treasures.cards
    assert card not in state.player(1).treasures.cards
    assert card.controller == 0
    assert card.owner == 1
    assert EventType.TREASURE_STOLEN in [event.type for event in runtime.history]


def test_a_stolen_item_arrives_tapped() -> None:
    """
    Stealing an item is not a way to use it twice in a turn.
    """
    runtime, state = started()

    card = equip(state, 1, item("test.loot_bag"))

    runtime.context._set_actor(0)
    runtime.context.apply("steal_treasure", [card])

    assert card.tapped is True


def test_an_item_can_be_destroyed() -> None:
    runtime, state = started()

    card = equip(state, 0, item("test.fragile"))

    runtime.context.apply("destroy_treasure", [card])
    runtime.run()

    assert card not in state.player(0).treasures.cards
    assert card in state.treasure_discard.cards
    assert EventType.TREASURE_DESTROYED in [event.type for event in runtime.history]


def test_an_eternal_item_survives_destruction_and_theft() -> None:
    runtime, state = started()

    card = equip(state, 1, item("test.bound", tags=("eternal",)))

    runtime.context._set_actor(0)

    assert runtime.context.apply("destroy_treasure", [card]) == 0
    assert runtime.context.apply("steal_treasure", [card]) == 0
    assert card in state.player(1).treasures.cards


def test_a_starting_item_is_eternal_without_saying_so() -> None:
    definition = item("test.starter", card_type=CardType.STARTING_ITEM)

    assert definition.is_eternal is True

    runtime, state = started()
    card = equip(state, 1, definition)

    runtime.context._set_actor(0)

    assert runtime.context.apply("steal_treasure", [card]) == 0
    assert card in state.player(1).treasures.cards


def test_a_thief_cannot_steal_from_themselves() -> None:
    runtime, state = started()

    card = equip(state, 0, item("test.mine"))

    runtime.context._set_actor(0)

    assert runtime.context.apply("steal_treasure", [card]) == 0


# ----------------------------------------------------------------------
# Curses
# ----------------------------------------------------------------------


def curse_card(card_id="test.curse", *, statics=(), abilities=()):
    return make_definition(
        card_id,
        card_type=CardType.CURSE,
        abilities=abilities,
        statics=statics,
    )


def test_a_curse_attaches_to_a_player() -> None:
    runtime, state = started()

    curse = make_instance(curse_card(), controller=0, owner=0, instance_id="c:1")

    runtime.context._set_source(curse)
    runtime.context.apply("attach_curse", [state.player(1)])
    runtime.run()

    assert curse in state.player(1).curses.cards
    assert curse.controller == 1
    assert state.player(1).curse_count == 1


def test_a_curse_is_in_play_and_its_statics_count() -> None:
    runtime, state = started()

    curse = make_instance(
        curse_card(statics=(Static(ATTACK, -1),)),
        controller=0,
        owner=0,
        instance_id="c:1",
    )

    runtime.context._set_source(curse)
    runtime.context.apply("attach_curse", [state.player(1)])

    assert curse in cards_in_play(state)
    assert bonus(state, ATTACK, 1) == -1


def test_a_curse_reacts_to_events_like_anything_else_in_play() -> None:
    runtime, state = started()

    curse = make_instance(
        curse_card(
            abilities=(
                Ability(
                    trigger="turn_start",
                    effects=({"effect": "deal_damage", "amount": 1, "target": "controller"},),
                ),
            )
        ),
        controller=0,
        owner=0,
        instance_id="c:1",
    )

    runtime.context._set_source(curse)
    runtime.context.apply("attach_curse", [state.player(1)])
    runtime.run()

    before = state.player(1).hp

    runtime.submit(Command(type=CommandType.END_PHASE, player=0))
    runtime.submit(Command(type=CommandType.END_TURN, player=0))

    assert state.player(1).hp == before - 1


def test_a_curse_can_be_removed() -> None:
    runtime, state = started()

    curse = make_instance(curse_card(), controller=0, owner=0, instance_id="c:1")

    runtime.context._set_source(curse)
    runtime.context.apply("attach_curse", [state.player(1)])
    runtime.context._set_source(None)

    runtime.context.apply("remove_curse", [curse])
    runtime.run()

    assert state.player(1).curse_count == 0
    assert curse in state.loot_discard.cards


def test_attaching_without_a_card_is_refused() -> None:
    runtime, state = started()

    with pytest.raises(EffectExecutionError):
        runtime.context.apply("attach_curse", [state.player(0)])


def test_a_curse_played_as_loot_is_not_also_discarded() -> None:
    """
    A card that put itself into play stays there; discarding it as well would
    leave the same card in two places.
    """
    runtime, state = started()

    definition = make_definition(
        "test.hex",
        card_type=CardType.LOOT,
        abilities=(
            Ability(
                trigger="on_play",
                effects=({"effect": "attach_curse", "target": "opponents"},),
            ),
        ),
    )

    card = CardInstance(definition=definition, instance_id="loot:hex")
    state.player(0).hand.cards.insert(0, card)

    runtime.submit(
        Command(type=CommandType.PLAY_LOOT, player=0, payload={"index": 0})
    )

    assert card in state.player(1).curses.cards
    assert card not in state.loot_discard.cards


# ----------------------------------------------------------------------
# Rooms
# ----------------------------------------------------------------------


def room_card(card_id="test.room", *, statics=(), abilities=()):
    return make_definition(
        card_id,
        card_type=CardType.ROOM,
        abilities=abilities,
        statics=statics,
    )


def stock_rooms(state, count=2):
    rooms = [
        CardInstance(
            definition=room_card(f"test.room{index}"),
            instance_id=f"room:{index}",
            controller=None,
            owner=None,
        )
        for index in range(count)
    ]

    for room in rooms:
        state.room_deck.add_top(room)

    return rooms


def test_entering_a_room_turns_it_face_up() -> None:
    runtime, state = started()

    rooms = stock_rooms(state)

    runtime.context.apply("enter_room", [])
    runtime.run()

    assert state.room_area.cards == [rooms[-1]]
    assert EventType.ON_ENTER in [event.type for event in runtime.history]


def test_a_new_room_replaces_the_old_one() -> None:
    runtime, state = started()

    rooms = stock_rooms(state)

    runtime.context.apply("enter_room", [])
    runtime.context.apply("enter_room", [])
    runtime.run()

    assert len(state.room_area) == 1
    assert rooms[-1] in state.room_discard.cards
    assert EventType.ON_LEAVE in [event.type for event in runtime.history]


def test_a_room_is_in_play_for_everybody() -> None:
    runtime, state = started(players=3)

    state.room_deck.add_top(
        CardInstance(
            definition=room_card(statics=(Static(ATTACK, 1, scope="all_players"),)),
            instance_id="room:aura",
            controller=None,
            owner=None,
        )
    )

    runtime.context.apply("enter_room", [])

    assert bonus(state, ATTACK, 0) == 1
    assert bonus(state, ATTACK, 1) == 1
    assert bonus(state, ATTACK, 2) == 1


def test_leaving_closes_the_room() -> None:
    runtime, state = started()

    stock_rooms(state, count=1)

    runtime.context.apply("enter_room", [])
    runtime.context.apply("leave_room", [])
    runtime.run()

    assert state.room_area.cards == []
    assert len(state.room_discard) == 1


def test_entering_with_an_empty_deck_does_nothing() -> None:
    runtime, state = started()

    assert runtime.context.apply("enter_room", []) == 0
    assert state.room_area.cards == []


# ----------------------------------------------------------------------
# Slots refill, however they emptied
# ----------------------------------------------------------------------


def _dealt_game() -> Any:
    """
    A real deal, because a stocked treasure deck is the point of these.

    ``make_game`` builds a bare state with no treasure deck behind the shop, so
    a refill there would have nothing to refill from and the test would pass by
    proving nothing.
    """
    from pathlib import Path

    from fsme.api import load_content
    from fsme.game import Game

    library = load_content(Path(__file__).resolve().parents[1] / "content")
    game = Game.from_content(library, ["Ann", "Bo"], seed=1)

    game.start()

    return game


def test_a_shop_slot_refills_however_it_was_emptied() -> None:
    """
    COMPREHENSIVE_RULES.md §9: "A slot refills as soon as it is empty."

    It used to refill only when a purchase emptied it, because the refill was
    called from the purchase. A card that took, stole or destroyed a shop item
    left the hole open for the rest of the game — five games in sixty ended
    with a short shop and a full treasure deck behind it.

    The refill lives with the state-based actions now, beside the one that
    fills the monster slots, so every way of emptying a slot is followed by the
    same refill.
    """
    from fsme.rules import SHOP_SLOTS

    game = _dealt_game()
    state = game.state

    assert len(state.treasure_shop) == SHOP_SLOTS
    assert state.treasure_deck.cards

    # Taken, not bought: whatever a card does to a shop item, the slot is empty
    # afterwards and the rules do not care how it got that way.
    taken = state.treasure_shop.draw()

    assert len(state.treasure_shop) == SHOP_SLOTS - 1

    # Any accepted command lets the engine settle, which is when slots refill.
    assert game.submit(
        Command(type=CommandType.END_PHASE, player=0)
    ).accepted

    assert len(state.treasure_shop) == SHOP_SLOTS, (
        "the shop was left short after a card removed an item"
    )
    assert all(card is not taken for card in state.treasure_shop.cards)


def test_an_empty_shop_refills_to_every_slot() -> None:
    """
    Both slots, not only the one the engine last noticed.
    """
    from fsme.rules import SHOP_SLOTS

    game = _dealt_game()
    state = game.state

    while state.treasure_shop.cards:
        state.treasure_shop.draw()

    assert game.submit(Command(type=CommandType.END_PHASE, player=0)).accepted

    assert len(state.treasure_shop) == SHOP_SLOTS


def test_a_shop_stays_short_when_the_deck_is_out() -> None:
    """
    A slot that cannot be filled is not an error, and nothing is invented to
    fill it.
    """
    game = _dealt_game()
    state = game.state

    state.treasure_deck.clear()
    state.treasure_shop.draw()

    assert game.submit(Command(type=CommandType.END_PHASE, player=0)).accepted

    assert len(state.treasure_shop) == 1
    assert game.runtime.is_stable()
