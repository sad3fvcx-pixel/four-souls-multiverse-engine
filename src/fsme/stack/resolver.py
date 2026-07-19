# src/fsme/stack/resolver.py

"""
Stack resolver for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .item import StackItem
from .result import StackResult


class StackResolver:
    """
    Resolves items removed from the game stack.

    Concrete effect execution will be implemented by the
    effect system. For now this class provides the common
    interface used by the engine.
    """

    def resolve(self, item: StackItem) -> StackResult:
        """
        Resolve a single stack item.
        """
        return StackResult.ok(
            message=f"Resolved '{item.effect}'."
        )