# src/fsme/events/event.py

"""
Base event class for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .types import EventType


class EventStatus(StrEnum):
    """
    Lifecycle position of an event.
    """

    CREATED = "created"
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"



@dataclass(slots=True)
class Event:
    """
    Represents a single event emitted by the engine.

    Events carry data only. They never contain executable code.

    EVENT_SYSTEM.md lists a timestamp among the event fields; the engine stores
    a monotonic ``sequence`` instead, because wall-clock values would make two
    runs of the same seed differ and break replay equality.
    """

    type: EventType

    source: Any | None = None
    controller: int | None = None

    targets: list[Any] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    event_id: str = ""
    sequence: int = 0

    status: EventStatus = EventStatus.CREATED

    @property
    def cancelled(self) -> bool:
        """
        Return True if this event will not resolve.
        """
        return self.status is EventStatus.CANCELLED

    def cancel(self) -> None:
        """
        Prevent this event from resolving.

        A cancelled event still exists in the replay log.
        """
        self.status = EventStatus.CANCELLED

    def mark_resolving(self) -> None:
        self.status = EventStatus.RESOLVING

    def mark_resolved(self) -> None:
        self.status = EventStatus.RESOLVED

    def get(self, key: str, default: Any = None) -> Any:
        """
        Read a payload value.
        """
        return self.payload.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Store a payload value.
        """
        self.payload[key] = value

    def has(self, key: str) -> bool:
        """
        Check whether the payload contains a key.
        """
        return key in self.payload

    def __str__(self) -> str:
        return f"{self.type}#{self.sequence}"
