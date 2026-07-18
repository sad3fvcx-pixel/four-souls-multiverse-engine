# src/fsme/commands/queue.py

"""
Command queue for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections import deque

from .base import Command


class CommandQueue:
    """
    FIFO queue of pending commands.
    """

    def __init__(self) -> None:
        self._queue: deque[Command] = deque()

    def __len__(self) -> int:
        return len(self._queue)

    def __bool__(self) -> bool:
        return bool(self._queue)

    def push(self, command: Command) -> None:
        """
        Add a command to the end of the queue.
        """
        self._queue.append(command)

    def pop(self) -> Command:
        """
        Remove and return the next command.
        """
        if not self._queue:
            raise IndexError("command queue is empty")

        return self._queue.popleft()

    def peek(self) -> Command:
        """
        Return the next command without removing it.
        """
        if not self._queue:
            raise IndexError("command queue is empty")

        return self._queue[0]

    def clear(self) -> None:
        """
        Remove all pending commands.
        """
        self._queue.clear()

    def is_empty(self) -> bool:
        """
        Return True if the queue contains no commands.
        """
        return not self._queue