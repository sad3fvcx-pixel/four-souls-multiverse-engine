# src/fsme/stack/handler.py

"""
Stack handler protocol for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Protocol

from .context import StackContext
from .result import StackResult


class StackHandler(Protocol):
    """
    Protocol implemented by all stack effect handlers.
    """

    def resolve(
        self,
        context: StackContext,
    ) -> StackResult:
        """
        Resolve a stack item.
        """
        ...