# src/fsme/events/filter.py

"""
Event filtering utilities for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Callable

from .event import Event

EventFilter = Callable[[Event], bool]


def accept_all(_: Event) -> bool:
    """
    Default filter that accepts every event.
    """
    return True


def cancelled_only(event: Event) -> bool:
    """
    Accept only cancelled events.
    """
    return event.cancelled


def active_only(event: Event) -> bool:
    """
    Accept only non-cancelled events.
    """
    return not event.cancelled