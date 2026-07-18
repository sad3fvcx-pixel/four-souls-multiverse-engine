# src/fsme/events/queue.py

"""
Event queue for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections import deque

from .event import Event


class EventQueue:
    """
    FIFO queue of pending events.
    """

    def __init__(self) -> None:
        self._queue: deque[Event] = deque()

    def __len__(self) -> int:
        return len(self._queue)

    def __bool__(self) -> bool:
        return bool(self._queue)

    def push(self, event: Event) -> None:
        """
        Add an event to the end of the queue.
        """
        self._queue.append(event)

    def pop(self) -> Event:
        """
        Remove and return the next event.
        """
        if not self._queue:
            raise IndexError("event queue is empty")

        return self._queue.popleft()

    def peek(self) -> Event:
        """
        Return the next event without removing it.
        """
        if not self._queue:
            raise IndexError("event queue is empty")

        return self._queue[0]

    def clear(self) -> None:
        """
        Remove all pending events.
        """
        self._queue.clear()

    def is_empty(self) -> bool:
        """
        Return True if the queue contains no events.
        """
        return not self._queue