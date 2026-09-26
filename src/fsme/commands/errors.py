"""
Exceptions for the command subsystem.
"""

from __future__ import annotations

from fsme.util.errors import CommandValidationError, EngineError


class CommandError(EngineError):
    """
    Base exception for all command-related errors.
    """


class UnknownCommandError(CommandError):
    """
    Raised when no handler is registered for a command type.
    """


class CommandRegistrationError(CommandError):
    """
    Raised when a command type is given a second handler.
    """


class CommandExecutionError(CommandError):
    """
    Raised when a validated command fails while executing.

    This means the engine accepted something it should not have, so it points
    at a gap in validation rather than at the caller.
    """


__all__ = [
    "CommandError",
    "CommandExecutionError",
    "CommandRegistrationError",
    "CommandValidationError",
    "UnknownCommandError",
]
