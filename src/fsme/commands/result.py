# src/fsme/commands/result.py

"""
Command execution result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class CommandResult:
    """
    Result returned after executing a command.
    """

    success: bool
    value: Any = None
    message: str | None = None

    @classmethod
    def ok(cls, value: Any = None) -> "CommandResult":
        """
        Create a successful result.
        """
        return cls(
            success=True,
            value=value,
        )

    @classmethod
    def fail(cls, message: str) -> "CommandResult":
        """
        Create a failed result.
        """
        return cls(
            success=False,
            message=message,
        )

    def __bool__(self) -> bool:
        return self.success