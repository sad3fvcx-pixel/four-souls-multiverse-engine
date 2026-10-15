"""
Event bus, queue and lifecycle.
"""

from __future__ import annotations

import pytest

from fsme.events import Event, EventBus, EventQueue, EventStatus, EventType


def test_handlers_run_in_registration_order() -> None:
    bus = EventBus()
    calls: list[str] = []

    bus.subscribe(EventType.TURN_START, lambda event: calls.append("first"))
    bus.subscribe(EventType.TURN_START, lambda event: calls.append("second"))

    bus.emit(Event(type=EventType.TURN_START))

    assert calls == ["first", "second"]


def test_cancelling_stops_further_handlers() -> None:
    bus = EventBus()
    calls: list[str] = []

    def cancel(event: Event) -> None:
        calls.append("first")
        event.cancel()

    bus.subscribe(EventType.TURN_START, cancel)
    bus.subscribe(EventType.TURN_START, lambda event: calls.append("second"))

    event = bus.emit(Event(type=EventType.TURN_START))

    assert calls == ["first"]
    assert event.cancelled
    assert event.status is EventStatus.CANCELLED


def test_queue_is_first_in_first_out() -> None:
    queue = EventQueue()

    queue.push(Event(type=EventType.TURN_START))
    queue.push(Event(type=EventType.TURN_END))

    assert queue.pop().type is EventType.TURN_START
    assert queue.pop().type is EventType.TURN_END
    assert queue.is_empty()

    with pytest.raises(IndexError):
        queue.pop()


def test_event_type_values_match_dsl_trigger_names() -> None:
    """
    A card writes "turn_start"; the engine must answer to exactly that name.
    """
    assert str(EventType.TURN_START) == "turn_start"
    assert str(EventType.AFTER_DAMAGE) == "after_damage"
    assert EventType("monster_killed") is EventType.MONSTER_KILLED


def test_events_carry_no_wall_clock() -> None:
    """
    Determinism forbids timestamps; ordering comes from the sequence number.
    """
    event = Event(type=EventType.TURN_START)

    assert not hasattr(event, "timestamp")
    assert event.sequence == 0
