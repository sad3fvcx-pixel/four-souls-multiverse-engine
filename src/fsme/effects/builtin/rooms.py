# src/fsme/effects/builtin/rooms.py

"""
Room effects.

A room is a card that stays face up in the room area, in play for everybody
until another one replaces it. The engine provides entering and leaving; when
a room may be entered, and what that costs, is a rule that belongs to the
content that defines rooms.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.events import EventType
from fsme.state import GameState

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry
from .decks import draw_from, restock


def _clear_room_area(ctx: EffectContext, state: GameState) -> None:
    """
    Send whatever is in the room area to the discard pile.
    """
    while state.room_area.cards:
        leaving = state.room_area.draw()

        state.room_discard.add_top(leaving)

        ctx.emit(
            EventType.ON_LEAVE,
            source=leaving,
            controller=ctx.actor,
        )


def enter_room(ctx: EffectContext, targets: Sequence[Any], count: int = 1) -> int:
    """
    Turn the top room of the deck face up, replacing the current one.
    """
    if count < 1:
        raise EffectExecutionError("enter_room count must be positive")

    state = ctx.state
    entered = 0

    for _ in range(count):
        if not state.room_deck.cards and not restock(ctx, "room"):
            break

        _clear_room_area(ctx, state)

        room = draw_from(ctx, "room")

        if room is None:
            break

        state.room_area.add_top(room)
        entered += 1

        ctx.emit(
            EventType.ON_ENTER,
            source=room,
            controller=ctx.actor,
        )

    return entered


def leave_room(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Close the current room without opening another.
    """
    state = ctx.state
    before = len(state.room_area)

    _clear_room_area(ctx, state)

    return before


def register(registry: EffectRegistry) -> None:
    """
    Register every room effect.
    """
    registry.register(
        "enter_room",
        enter_room,
        primary="count",
        description="Turn the top room face up, replacing the current one.",
    )
    registry.register(
        "leave_room",
        leave_room,
        description="Close the current room.",
    )
