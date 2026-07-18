# src/fsme/commands/dispatcher.py

"""
Command dispatcher for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from .base import Command
from .bus import CommandBus
from .handler import CommandHandler
from .result import CommandResult


class CommandDispatcher:
    """
    High-level interface for dispatching commands.
    """

    def __init__(self, bus: CommandBus | None = None) -> None:
        self._bus = bus or CommandBus()

    @property
    def bus(self) -> CommandBus:
        return self._bus

    def register(
        self,
        command_type: type[Command],
        handler: CommandHandler,
    ) -> None:
        self._bus.register(command_type, handler)

    def unregister(
        self,
        command_type: type[Command],
    ) -> None:
        self._bus.unregister(command_type)

    def dispatch(self, command: Command) -> CommandResult:
        return self._bus.execute(command)

    def clear(self) -> None:
        self._bus.clear()