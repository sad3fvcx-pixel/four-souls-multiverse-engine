# src/fsme/events/bus.py

"""
Event bus for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from .event import Event
from .types import EventType

EventHandler = Callable[[Event], Any]


class EventBus:
    """
    Simple synchronous event bus.

    Handlers are executed in registration order.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Register a handler for an event type.
        """
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Remove a previously registered handler.
        """
        handlers = self._handlers.get(event_type)
        if handlers is None:
            return

        try:
            handlers.remove(handler)
        except ValueError:
            return

        if not handlers:
            del self._handlers[event_type]

    def emit(self, event: Event) -> Event:
        """
        Dispatch an event to all registered handlers.

        Stops processing if the event is cancelled.
        """
        for handler in self._handlers.get(event.type, ()):
            handler(event)

            if event.cancelled:
                break

        return event

    def clear(self) -> None:
        """
        Remove all registered handlers.
        """
        self._handlers.clear()

    def has_handlers(self, event_type: EventType) -> bool:
        """
        Return True if at least one handler is registered.
        """
        return bool(self._handlers.get(event_type))

    def handler_count(self, event_type: EventType) -> int:
        """
        Return the number of handlers for an event type.
        """
        return len(self._handlers.get(event_type, ()))