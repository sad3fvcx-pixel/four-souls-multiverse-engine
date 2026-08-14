# src/fsme/rules/slots.py

"""
Putting monsters into slots and taking them out again.

Every change to the monster area goes through here, for one reason: the area is
kept twice. ``monster_area`` is the truth — a row of slots, each with its own
pile — and ``active_monsters`` is the face-up card of each occupied slot, which
is what nearly everything else in the engine actually wants to look at. Two
records of one thing drift apart unless exactly one piece of code writes both,
and this is that piece.

The rules a slot follows are in COMPREHENSIVE_RULES.md §2, §7 and §9: a slot's
face-up card is its active monster, a monster revealed by attacking the deck
goes on top of one, and an empty slot refills.
"""

from __future__ import annotations

from typing import Any

from fsme.state import GameState, MonsterSlot


def open_area(state: GameState, slots: int | None = None) -> None:
    """
    Lay out the row of slots, keeping whatever is already standing in it.
    """
    wanted = state.monster_slots if slots is None else int(slots)

    while len(state.monster_area) < wanted:
        state.monster_area.append(MonsterSlot())

    sync(state)


def slot_of(state: GameState, card: Any) -> int | None:
    """
    Which slot a monster is standing in, buried or not.
    """
    for index, slot in enumerate(state.monster_area):
        for held in slot.cards:
            if held is card:
                return index

    return None


def empty_slot(state: GameState) -> int | None:
    """
    The first slot with nothing in it, if the area has one.
    """
    for index, slot in enumerate(state.monster_area):
        if slot.is_empty:
            return index

    return None


def place(state: GameState, card: Any, slot: int | None = None) -> int:
    """
    Put a monster into a slot, face up.

    With no slot named it goes into the first empty one, and into a new slot if
    the row is full — a card that adds a monster to a full board is asking for
    somewhere to put it, and the alternative is losing the monster.
    """
    _make_room(state)

    index = slot if slot is not None else empty_slot(state)

    if index is None or not 0 <= index < len(state.monster_area):
        state.monster_area.append(MonsterSlot())

        index = len(state.monster_area) - 1

    state.monster_area[index].push(card)

    sync(state)

    return index


def cover(state: GameState, card: Any, slot: int | None = None) -> int:
    """
    Put a monster on top of the one already in a slot.

    COMPREHENSIVE_RULES.md §7: this is what a monster revealed by attacking the
    monster deck does. With no slot named it covers the first occupied one, and
    with nothing to cover it simply stands in an empty slot.
    """
    if slot is None:
        occupied = [
            index
            for index, standing in enumerate(state.monster_area)
            if not standing.is_empty
        ]

        slot = occupied[0] if occupied else None

    return place(state, card, slot)


def remove(state: GameState, card: Any) -> int | None:
    """
    Take a monster out of the area, whichever slot it was in.

    Whatever it was covering comes back face up. The slot itself stays: an
    empty slot is a place waiting to be filled, not a gap in the row.
    """
    index = slot_of(state, card)

    if index is None:
        return None

    state.monster_area[index].remove(card)

    sync(state)

    return index


def _make_room(state: GameState) -> None:
    """
    Keep the row at least as long as the game says it is.
    """
    while len(state.monster_area) < state.monster_slots:
        state.monster_area.append(MonsterSlot())


def sync(state: GameState) -> None:
    """
    Bring the face-up view back in line with the slots.
    """
    state.active_monsters.cards[:] = [
        slot.active for slot in state.monster_area if slot.active is not None
    ]
