# src/fsme/events/event.py

"""
Base event class for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .types import EventType


@dataclass(slots=True)
class Event:
    """
    Represents a single event emitted by the engine.
    """

    type: EventType

    source: Any | None = None
    target: Any | None = None

    payload: dict[str, Any] = field(default_factory=dict)

    cancelled: bool = False

    def cancel(self) -> None:
        """
        Prevent further processing of this event.
        """
        self.cancelled = True

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