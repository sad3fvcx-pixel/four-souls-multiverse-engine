# src/fsme/stack/stack.py

"""
Game stack implementation for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Iterator

from .item import StackItem


class Stack:
    """
    LIFO stack used for abilities, loot, and triggered effects.
    """

    def __init__(self) -> None:
        self._items: list[StackItem] = []

    def __len__(self) -> int:
        return len(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    def __iter__(self) -> Iterator[StackItem]:
        return iter(self._items)

    def push(self, item: StackItem) -> None:
        """
        Push an item onto the top of the stack.
        """
        self._items.append(item)

    def pop(self) -> StackItem:
        """
        Remove and return the top stack item.
        """
        if not self._items:
            raise IndexError("stack is empty")

        return self._items.pop()

    def peek(self) -> StackItem:
        """
        Return the top stack item without removing it.
        """
        if not self._items:
            raise IndexError("stack is empty")

        return self._items[-1]

    def clear(self) -> None:
        """
        Remove all items from the stack.
        """
        self._items.clear()

    def is_empty(self) -> bool:
        """
        Return True if the stack contains no items.
        """
        return not self._items