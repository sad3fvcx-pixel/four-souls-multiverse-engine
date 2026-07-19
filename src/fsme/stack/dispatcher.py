# src/fsme/stack/dispatcher.py

"""
Stack dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .handler import StackHandler
from .item import StackItem
from .resolver import StackResolver
from .result import StackResult


class StackDispatcher:
    """
    Dispatches stack items to the resolver.

    Serves as the public entry point for stack resolution.
    """

    def __init__(
        self,
        resolver: StackResolver | None = None,
    ) -> None:
        self._resolver = resolver or StackResolver()

    @property
    def resolver(self) -> StackResolver:
        return self._resolver

    def dispatch(self, item: StackItem) -> StackResult:
        """
        Resolve a single stack item.
        """
        return self._resolver.resolve(item)

    def set_resolver(
        self,
        resolver: StackResolver,
    ) -> None:
        """
        Replace the active resolver.
        """
        self._resolver = resolver