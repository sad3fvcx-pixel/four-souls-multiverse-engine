# src/fsme/commands/bus.py

"""
Command bus for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import Command
from .result import CommandResult

CommandHandler = Callable[[Command], CommandResult]


class CommandBus:
    """
    Dispatches commands to registered handlers.
    """

    def __init__(self) -> None:
        self._handlers: dict[type[Command], CommandHandler] = {}

    def register(
        self,
        command_type: type[Command],
        handler: CommandHandler,
    ) -> None:
        """
        Register a handler for a command type.
        """
        self._handlers[command_type] = handler

    def unregister(
        self,
        command_type: type[Command],
    ) -> None:
        """
        Remove a registered handler.
        """
        self._handlers.pop(command_type, None)

    def execute(self, command: Command) -> CommandResult:
        """
        Execute a command.
        """
        handler = self._handlers.get(type(command))

        if handler is None:
            return CommandResult.fail(
                f"No handler registered for {type(command).__name__}"
            )

        return handler(command)

    def has_handler(
        self,
        command_type: type[Command],
    ) -> bool:
        """
        Return True if a handler is registered.
        """
        return command_type in self._handlers

    def clear(self) -> None:
        """
        Remove all registered handlers.
        """
        self._handlers.clear()