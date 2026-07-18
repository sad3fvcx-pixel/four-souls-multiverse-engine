# src/fsme/commands/errors.py

"""
Exceptions for the command subsystem.
"""

from __future__ import annotations

from fsme.util.errors import (
    CommandValidationError,
    EngineError,
)


class CommandError(EngineError):
    """
    Base exception for the command subsystem.
    """


class CommandDispatchError(CommandError):
    """
    Raised when a command cannot be dispatched.
    """


class CommandHandlerError(CommandError):
    """
    Raised when a command handler fails.
    """


class CommandRegistrationError(CommandError):
    """
    Raised when an invalid handler registration is attempted.
    """


class UnknownCommandError(CommandError):
    """
    Raised when no handler exists for a command.
    """


class InvalidCommandError(CommandValidationError):
    """
    Raised when a command fails validation.
    """