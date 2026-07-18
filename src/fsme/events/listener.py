# src/fsme/events/listener.py

"""
Listener protocol for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Protocol

from .event import Event


class EventListener(Protocol):
    """
    Protocol implemented by event listeners.
    """

    def __call__(self, event: Event) -> None:
        ...