# src/fsme/commands/base.py

"""
Base command class for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Command:
    """
    Base class for every engine command.

    Commands describe an action that should be executed by the engine.
    They contain data only and should not implement game logic.
    """

    source: Any | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Return a payload value.
        """
        return self.payload.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Store a payload value.
        """
        self.payload[key] = value

    def has(self, key: str) -> bool:
        """
        Return True if the payload contains the given key.
        """
        return key in self.payload