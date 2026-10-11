# src/fsme/commands/__init__.py

"""
Command subsystem exports.

Commands are the only way into the engine. Players, AI, networking, replay and
tests all arrive through here.
"""

from .command import Command
from .errors import (
    CommandError,
    CommandExecutionError,
    CommandRegistrationError,
    CommandValidationError,
    UnknownCommandError,
)
from .handler import CommandHandler
from .registry import CommandRegistry
from .result import CommandResult
from .types import CommandType

__all__ = [
    "Command",
    "CommandHandler",
    "CommandRegistry",
    "CommandResult",
    "CommandType",
    "CommandError",
    "CommandExecutionError",
    "CommandRegistrationError",
    "CommandValidationError",
    "UnknownCommandError",
]
