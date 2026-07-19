# src/fsme/stack/__init__.py

"""
Stack subsystem exports.
"""

from .constants import (
    CARD_STACK_SOURCE,
    DEFAULT_STACK_LIMIT,
    PLAYER_STACK_SOURCE,
    REPLACEMENT_STACK_SOURCE,
    SYSTEM_STACK_SOURCE,
    TRIGGER_STACK_SOURCE,
)
from .context import StackContext
from .dispatcher import StackDispatcher
from .errors import (
    InvalidStackItemError,
    StackEmptyError,
    StackError,
    StackOverflowError,
    StackResolutionError,
)
from .handler import StackHandler
from .item import StackItem
from .resolver import StackResolver
from .result import StackResult
from .stack import Stack
from .utils import (
    ensure_stack_item,
    ensure_stack_items,
    is_stack_item,
    stack_item_name,
)

__all__ = [
    "Stack",
    "StackItem",
    "StackResult",
    "StackResolver",
    "StackDispatcher",
    "StackHandler",
    "StackContext",
    "StackError",
    "StackEmptyError",
    "StackResolutionError",
    "InvalidStackItemError",
    "StackOverflowError",
    "DEFAULT_STACK_LIMIT",
    "SYSTEM_STACK_SOURCE",
    "PLAYER_STACK_SOURCE",
    "CARD_STACK_SOURCE",
    "TRIGGER_STACK_SOURCE",
    "REPLACEMENT_STACK_SOURCE",
    "ensure_stack_item",
    "ensure_stack_items",
    "stack_item_name",
    "is_stack_item",
]