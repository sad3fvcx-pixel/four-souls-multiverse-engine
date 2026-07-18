# src/fsme/events/result.py

"""
Event dispatch result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from .event import Event


@dataclass(slots=True, frozen=True)
class EventResult:
    """
    Result returned after an event has been dispatched.
    """

    event: Event
    handlers_called: int
    cancelled: bool

    @classmethod
    def from_event(cls, event: Event, handlers_called: int) -> "EventResult":
        return cls(
            event=event,
            handlers_called=handlers_called,
            cancelled=event.cancelled,
        )

    @property
    def handled(self) -> bool:
        """
        Return True if at least one handler processed the event.
        """
        return self.handlers_called > 0