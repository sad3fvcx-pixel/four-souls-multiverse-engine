# src/fsme/events/priority.py

"""
Event listener priorities for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from enum import IntEnum


class EventPriority(IntEnum):
    """
    Listener execution priority.

    Higher priority listeners are executed first.
    """

    LOWEST = 0
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100

    def __str__(self) -> str:
        return self.name.lower()