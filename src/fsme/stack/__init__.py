# src/fsme/stack/__init__.py

"""
Stack subsystem exports.

The stack stores pending actions and enforces LIFO ordering. It does not
resolve them: resolution needs effects, targets and events, all of which sit
above the stack in the dependency order, so the Runtime owns it.
"""

from .errors import (
    InvalidStackItemError,
    StackEmptyError,
    StackError,
    StackOverflowError,
    StackResolutionError,
)
from .item import StackItem, StackItemStatus, StackItemType
from .stack import Stack

__all__ = [
    "Stack",
    "StackItem",
    "StackItemStatus",
    "StackItemType",
    "StackError",
    "StackEmptyError",
    "StackResolutionError",
    "InvalidStackItemError",
    "StackOverflowError",
]
