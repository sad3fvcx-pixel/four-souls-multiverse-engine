# src/fsme/logging/context.py

"""
Logging context for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .logger import Logger


@dataclass(slots=True)
class LoggingContext:
    """
    Shared context for logging operations.
    """

    logger: Logger = field(default_factory=Logger)

    values: dict[str, Any] = field(default_factory=dict)

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Return a stored context value.
        """
        return self.values.get(key, default)

    def set(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Store a context value.
        """
        self.values[key] = value

    def has(
        self,
        key: str,
    ) -> bool:
        """
        Return True if the key exists.
        """
        return key in self.values

    def remove(
        self,
        key: str,
    ) -> None:
        """
        Remove a stored value.
        """
        self.values.pop(key, None)

    def clear(self) -> None:
        """
        Remove all stored values.
        """
        self.values.clear()