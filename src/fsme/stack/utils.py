# src/fsme/stack/utils.py

"""
Utility functions for the stack subsystem.
"""

from __future__ import annotations

from collections.abc import Iterable

from .item import StackItem


def ensure_stack_item(obj: object) -> StackItem:
    """
    Ensure that an object is a StackItem.
    """
    if not isinstance(obj, StackItem):
        raise TypeError(
            f"Expected StackItem, got {type(obj).__name__}."
        )

    return obj


def ensure_stack_items(
    items: Iterable[object],
) -> list[StackItem]:
    """
    Validate an iterable of stack items.
    """
    return [ensure_stack_item(item) for item in items]


def stack_item_name(item: StackItem) -> str:
    """
    Return a human-readable name for a stack item.
    """
    return item.effect


def is_stack_item(obj: object) -> bool:
    """
    Check whether an object is a StackItem.
    """
    return isinstance(obj, StackItem)