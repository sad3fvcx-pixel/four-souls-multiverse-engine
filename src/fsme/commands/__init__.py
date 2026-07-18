# src/fsme/commands/__init__.py

"""
Command subsystem exports.
"""

from .base import Command
from .bus import CommandBus
from .constants import (
    CARD_COMMAND_SOURCE,
    DEFAULT_COMMAND_PRIORITY,
    MAX_COMMAND_DEPTH,
    PLAYER_COMMAND_SOURCE,
    SYSTEM_COMMAND_SOURCE,
)
from .context import CommandContext
from .dispatcher import CommandDispatcher
from .errors import (
    CommandDispatchError,
    CommandError,
    CommandHandlerError,
    CommandRegistrationError,
    InvalidCommandError,
    UnknownCommandError,
)
from .handler import CommandHandler
from .queue import CommandQueue
from .result import CommandResult
from .types import CommandType
from .utils import (
    command_name,
    ensure_command,
    ensure_commands,
    is_command_instance,
    is_command_type,
)

__all__ = [
    "Command",
    "CommandBus",
    "CommandContext",
    "CommandDispatcher",
    "CommandHandler",
    "CommandQueue",
    "CommandResult",
    "CommandType",
    "CommandError",
    "CommandDispatchError",
    "CommandHandlerError",
    "CommandRegistrationError",
    "UnknownCommandError",
    "InvalidCommandError",
    "DEFAULT_COMMAND_PRIORITY",
    "MAX_COMMAND_DEPTH",
    "SYSTEM_COMMAND_SOURCE",
    "PLAYER_COMMAND_SOURCE",
    "CARD_COMMAND_SOURCE",
    "ensure_command",
    "ensure_commands",
    "command_name",
    "is_command_instance",
    "is_command_type",
]