# src/fsme/events/dispatcher.py

"""
Convenience wrapper around the EventBus.
"""

from __future__ import annotations

from .bus import EventBus
from .event import Event
from .listener import EventListener
from .types import EventType


class EventDispatcher:
    """
    High-level interface used by the engine to work with events.
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus or EventBus()

    @property
    def bus(self) -> EventBus:
        return self._bus

    def subscribe(
        self,
        event_type: EventType,
        listener: EventListener,
    ) -> None:
        self._bus.subscribe(event_type, listener)

    def unsubscribe(
        self,
        event_type: EventType,
        listener: EventListener,
    ) -> None:
        self._bus.unsubscribe(event_type, listener)

    def dispatch(self, event: Event) -> Event:
        return self._bus.emit(event)

    def clear(self) -> None:
        self._bus.clear()