# src/fsme/events/subscription.py

"""
Event subscription for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from .filter import EventFilter, accept_all
from .listener import EventListener
from .types import EventType


@dataclass(slots=True)
class EventSubscription:
    """
    Represents a single event subscription.
    """

    event_type: EventType
    listener: EventListener
    event_filter: EventFilter = accept_all
    enabled: bool = True

    def accepts(self, event) -> bool:
        """
        Return True if this subscription should receive the event.
        """
        return self.enabled and self.event_filter(event)

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False
