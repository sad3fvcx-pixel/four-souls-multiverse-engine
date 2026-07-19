# src/fsme/cards/handler.py

"""
Card handler protocol for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Protocol

from .context import CardContext
from .result import CardResult


class CardHandler(Protocol):
    """
    Protocol implemented by all card handlers.
    """

    def execute(
        self,
        context: CardContext,
    ) -> CardResult:
        """
        Execute a card-related operation.
        """
        ...