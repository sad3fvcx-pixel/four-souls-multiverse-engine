# src/fsme/commands/utils.py

"""
Utility functions for the command subsystem.
"""

from __future__ import annotations

from collections.abc import Iterable

from .base import Command


def ensure_command(obj: object) -> Command:
    """
    Ensure that an object is a Command instance.
    """
    if not isinstance(obj, Command):
        raise TypeError(
            f"Expected Command, got {type(obj).__name__}."
        )

    return obj


def ensure_commands(
    commands: Iterable[object],
) -> list[Command]:
    """
    Validate an iterable of commands.
    """
    return [ensure_command(command) for command in commands]


def command_name(command: Command | type[Command]) -> str:
    """
    Return the class name of a command.
    """
    if isinstance(command, type):
        return command.__name__

    return command.__class__.__name__


def is_command_instance(obj: object) -> bool:
    """
    Check whether an object is a Command instance.
    """
    return isinstance(obj, Command)


def is_command_type(obj: object) -> bool:
    """
    Check whether an object is a Command subclass.
    """
    return (
        isinstance(obj, type)
        and issubclass(obj, Command)
    )