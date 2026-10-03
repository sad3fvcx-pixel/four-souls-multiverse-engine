# src/fsme/commands/registry.py

"""
Command registry for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .errors import CommandRegistrationError, UnknownCommandError
from .handler import CommandHandler
from .types import CommandType


class CommandRegistry:
    """
    Maps command types to the rules that implement them.

    An expansion may add command types; an unknown one is rejected rather than
    guessed at, which is what keeps "commands never bypass validation" true
    even for content the engine has never seen.
    """

    def __init__(self) -> None:
        self._handlers: dict[CommandType, CommandHandler] = {}

    def __contains__(self, command_type: object) -> bool:
        return command_type in self._handlers

    def __len__(self) -> int:
        return len(self._handlers)

    def register(
        self,
        command_type: CommandType,
        handler: CommandHandler,
    ) -> CommandHandler:
        """
        Register the handler for a command type.
        """
        if command_type in self._handlers:
            raise CommandRegistrationError(
                f"command '{command_type}' already has a handler"
            )

        self._handlers[command_type] = handler

        return handler

    def handler(self, command_type: CommandType) -> CommandHandler:
        """
        Return the handler for a command type.
        """
        try:
            return self._handlers[command_type]
        except KeyError:
            raise UnknownCommandError(
                f"no handler registered for command '{command_type}'"
            ) from None

    def types(self) -> frozenset[CommandType]:
        """
        Return every command type the engine can currently accept.
        """
        return frozenset(self._handlers)
