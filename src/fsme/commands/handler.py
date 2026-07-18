# src/fsme/commands/handler.py

"""
Command handler protocol for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from typing import Protocol

from .base import Command
from .result import CommandResult


class CommandHandler(Protocol):
    """
    Protocol implemented by command handlers.
    """

    def __call__(self, command: Command) -> CommandResult:
        ...