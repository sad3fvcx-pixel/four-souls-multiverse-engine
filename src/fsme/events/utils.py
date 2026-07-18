# src/fsme/events/utils.py

"""
Utility helpers for the event subsystem.
"""

from __future__ import annotations

from .event import Event
from .types import EventType


def create_event(
    event_type: EventType,
    **payload: object,
) -> Event:
    """
    Create an Event with payload.
    """
    return Event(
        type=event_type,
        payload=dict(payload),
    )


def is_cancelled(event: Event) -> bool:
    """
    Return True if the event has been cancelled.
    """
    return event.cancelled


def ensure_not_cancelled(event: Event) -> None:
    """
    Raise RuntimeError if the event is cancelled.
    """
    if event.cancelled:
        raise RuntimeError("event has been cancelled")